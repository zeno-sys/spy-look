"""基于 ffmpeg silencedetect 的 VAD 静音切分。

## 背景

长音频直接送 ASR 会触发接口限制（硅基流动：≤50MB、≤1h）或超时。
固定时长切分（如每 10 分钟一刀）容易在句子中间截断，影响识别质量。

本模块的目标：只在「句间停顿 / 静音处」切分，使每段既满足 API 限制，又尽量保持语义完整。

## 方案选型

| 方案              | 依赖           | 适用场景           | 结论     |
|-------------------|----------------|--------------------|----------|
| ffmpeg silencedetect | 无（已有 ffmpeg） | 单人讲解、播客     | **采用** |
| Silero VAD        | torch          | 嘈杂 / 多人        | 备选升级 |
| webrtcvad         | 轻量库         | 实时流             | 不采用   |

讲解类音频句间停顿明显（≥350ms），能量阈值法足够；零新增 Python 依赖。

## 整体流程

    MP4 → WAV（moviepy）
        → normalize_wav_for_asr()   # 16kHz 单声道，压缩体积
        → detect_silences()         # ffmpeg 找静音区间
        → compute_max_chunk_sec()   # 综合时长 / 体积算单段上限
        → find_chunk_boundaries()   # 在静音处选切点
        → split_wav_at_boundaries() # ffmpeg 无重编码切分
        → 逐段 ASR（voice_to_text.py 并行调用）

## 核心算法：静音检测 + 智能选切点

### 1. 静音检测（detect_silences）

    ffmpeg -af silencedetect=noise=-35dB:d=0.35

- noise=-35dB：低于此能量视为静音
- d=0.35：静音持续 ≥350ms 才报告（过滤换气，保留句间停顿）

### 2. 单段上限（compute_max_chunk_sec）

    effective = min(MAX_CHUNK_SEC, MAX_FILE_BYTES / bytes_per_sec × 0.9)

同时约束「时长」和「文件体积」。44100Hz 立体声体积远大于时长限制，
因此上游需先归一化为 16kHz mono（约 32KB/s，4min ≈ 7.5MB）。

### 3. 切点选取（find_chunk_boundaries）

贪心策略，在接近单段上限时选附近**最长静音的中点**作为切点：

    cuts = [0.0]
    while 未覆盖全长:
        target = cuts[-1] + max_chunk_sec
        在 [target ± search_window] 内找最长静音
        cut_point = 静音中点 (start + end) / 2
        若 cut_point 未前进 → fallback 硬切 target（防死循环）
        cuts.append(cut_point)
    cuts.append(total_duration)

切在静音正中间，前后各留半段静音作缓冲，最小化 ASR 上下文损失。

## 默认参数与调优

| 参数              | 默认    | 调优方向                              |
|-------------------|---------|---------------------------------------|
| noise_db          | -35     | 切在句中 → 降到 -40；切太碎 → 升到 -30 |
| min_duration      | 0.35s   | 切太碎 → 增到 0.5–0.8                 |
| max_chunk_sec     | 4min    | 见工具配置 asr.max_chunk_sec       |
| max_file_bytes    | 20MB    | 见工具配置 asr.max_file_bytes      |
| search_window     | 60s     | 自动截断为 max_chunk_sec × 0.5        |

## 公开 API

- get_wav_duration()          — 读取 WAV 时长
- normalize_wav_for_asr()     — 16kHz 单声道归一化
- compute_max_chunk_sec()     — 计算单段允许最大秒数
- detect_silences()           — 检测静音区间
- find_chunk_boundaries()     — 选取切分边界
- split_wav_at_boundaries()   — 按边界导出 WAV 片段
- format_timestamp()          — 秒 → HH:MM:SS

## 局限与升级

- silencedetect 是能量阈值法，无法区分背景音乐静音与说话停顿；无 BGM 的讲解场景无影响。
- 若后续处理会议 / 嘈杂音频，可替换 detect_silences() 为 Silero VAD，
  find_chunk_boundaries() 及后续流程无需改动。
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import wave
from pathlib import Path

from config_loader import load_config, reload_config

_cfg = load_config()
_vad = _cfg["vad"]
_asr = _cfg["asr"]

FFMPEG_PATH = _cfg["ffmpeg_path"]


def refresh_config() -> None:
    """重新加载运行时配置并刷新模块级变量。"""
    global _cfg, _vad, _asr, FFMPEG_PATH

    _cfg = reload_config()
    _vad = _cfg["vad"]
    _asr = _cfg["asr"]
    FFMPEG_PATH = _cfg["ffmpeg_path"]


_SILENCE_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([\d.]+)")


def get_wav_duration(wav_path: str | Path) -> float:
    """读取 WAV 文件时长（秒）。"""
    with wave.open(str(wav_path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def normalize_wav_for_asr(
    wav_path: str | Path,
    sample_rate: int = _vad["sample_rate"],
) -> str:
    """转为 16kHz 单声道 PCM，降低体积并符合 ASR 输入习惯。"""
    wav_path = Path(wav_path)
    out_path = wav_path.with_name(f"{wav_path.stem}_asr.wav")
    command = [
        _get_ffmpeg_bin(),
        "-y",
        "-i",
        str(wav_path),
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(out_path),
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = _safe_decode(result.stderr)
        raise RuntimeError(f"ffmpeg 音频归一化失败: {stderr}")
    return str(out_path)


def compute_max_chunk_sec(
    total_duration: float,
    file_size: int,
    max_chunk_sec: float,
    max_file_bytes: int,
) -> float:
    """综合时长与体积上限，计算单段允许的最大秒数。"""
    if total_duration <= 0 or file_size <= 0:
        return max_chunk_sec
    bytes_per_sec = file_size / total_duration
    size_limited_sec = max_file_bytes / bytes_per_sec * 0.9
    return min(max_chunk_sec, size_limited_sec)


def detect_silences(
    wav_path: str | Path,
    noise_db: float = _vad["noise_db"],
    min_duration: float = _vad["min_duration"],
) -> list[tuple[float, float]]:
    """用 ffmpeg silencedetect 检测静音区间，返回 [(start, end), ...]。"""
    wav_path = Path(wav_path)
    if not wav_path.exists():
        raise FileNotFoundError(f"文件不存在: {wav_path}")

    command = [
        _get_ffmpeg_bin(),
        "-i",
        str(wav_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stderr = _safe_decode(result.stderr)
    if result.returncode not in (0, 255):
        raise RuntimeError(f"ffmpeg silencedetect 失败: {stderr}")

    silences: list[tuple[float, float]] = []
    pending_start: float | None = None
    for line in stderr.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue
        end_match = _SILENCE_END_RE.search(line)
        if end_match and pending_start is not None:
            silences.append((pending_start, float(end_match.group(1))))
            pending_start = None

    return silences


def find_chunk_boundaries(
    total_duration: float,
    silences: list[tuple[float, float]],
    max_chunk_sec: float = _asr["max_chunk_sec"],
    search_window: float = _vad["search_window"],
    min_silence_sec: float = _vad["min_silence_sec"],
) -> list[float]:
    """
    在静音处选取切分点，返回单调递增边界 [0, cut1, cut2, ..., total_duration]。
    """
    if total_duration <= max_chunk_sec:
        return [0.0, total_duration]

    qualified = [
        (start, end)
        for start, end in silences
        if end - start >= min_silence_sec
    ]

    min_advance = min(max_chunk_sec * 0.05, 5.0)
    window = min(search_window, max_chunk_sec * 0.5)

    cuts = [0.0]
    while cuts[-1] < total_duration - min_advance:
        target = min(cuts[-1] + max_chunk_sec, total_duration)
        if target >= total_duration - min_advance:
            break

        window_start = max(cuts[-1] + min_advance, target - window)
        window_end = min(total_duration, target + window)

        best: tuple[float, float] | None = None
        best_duration = 0.0
        for start, end in qualified:
            if end <= window_start or start >= window_end:
                continue
            silence_duration = end - start
            if silence_duration > best_duration:
                best_duration = silence_duration
                best = (start, end)

        if best is not None:
            cut_point = (best[0] + best[1]) / 2
            if cut_point <= cuts[-1] + min_advance:
                cut_point = target
        else:
            cut_point = target

        cuts.append(min(cut_point, total_duration))

    if cuts[-1] < total_duration:
        cuts.append(total_duration)

    return cuts


def split_wav_at_boundaries(
    wav_path: str | Path,
    boundaries: list[float],
    out_dir: str | Path | None = None,
) -> list[str]:
    """按边界切分 WAV，返回各片段路径（按时间顺序）。"""
    wav_path = Path(wav_path)
    if len(boundaries) < 2:
        raise ValueError("boundaries 至少需要两个时间点")

    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp(prefix="vad_chunks_"))
    else:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    chunk_paths: list[str] = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        duration = boundaries[i + 1] - start
        if duration <= 0:
            continue

        chunk_path = out_dir / f"chunk_{i:03d}.wav"
        command = [
            _get_ffmpeg_bin(),
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(wav_path),
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            str(chunk_path),
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            stderr = _safe_decode(result.stderr)
            raise RuntimeError(f"ffmpeg 切分失败 (段 {i}): {stderr}")

        chunk_paths.append(str(chunk_path))

    return chunk_paths


def format_timestamp(seconds: float) -> str:
    """秒数转为 HH:MM:SS。"""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _get_ffmpeg_bin() -> str:
    ffmpeg_bin = Path(FFMPEG_PATH).expanduser()
    if ffmpeg_bin.exists():
        return str(ffmpeg_bin)
    return "ffmpeg"


def _safe_decode(content: bytes | str | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    for encoding in ("utf-8", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")
