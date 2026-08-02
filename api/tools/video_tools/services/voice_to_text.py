"""MP4 语音转文本（硅基流动 ASR）"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from contextvars import ContextVar
from pathlib import Path

import httpx

from config_loader import load_config, reload_config
from vad_split import (
    compute_max_chunk_sec,
    detect_silences,
    find_chunk_boundaries,
    format_timestamp,
    get_wav_duration,
    normalize_wav_for_asr,
    refresh_config as refresh_vad_config,
    split_wav_at_boundaries,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_progress_cb: ContextVar[Callable[[str], None] | None] = ContextVar("progress_cb", default=None)

def _resolve_ffmpeg(configured: str) -> str:
    path = (configured or "").strip()
    if path:
        return path
    found = shutil.which("ffmpeg")
    return found or "ffmpeg"


_cfg = load_config()
_asr = _cfg["asr"]

FFMPEG_PATH = _resolve_ffmpeg(_cfg["ffmpeg_path"])
os.environ["FFMPEG_BINARY"] = FFMPEG_PATH

MAX_CHUNK_SEC = float(_asr["max_chunk_sec"])
MAX_FILE_BYTES = int(_asr["max_file_bytes"])
ASR_PARALLEL_WORKERS = int(_asr["parallel_workers"])
ASR_MAX_RETRIES = int(_asr["max_retries"])
ASR_REQUEST_TIMEOUT_SEC = int(_asr["request_timeout_sec"])

DEFAULT_ASR_MODEL = _asr["model"]
base_url = _asr["base_url"]
api_key = _asr["api_key"]

# 音频转文字支持的常见音频格式
SUPPORTED_AUDIO_SUFFIXES = {
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".opus",
    ".wma", ".aiff", ".aif", ".amr", ".mka",
}


def refresh_config() -> None:
    """重新加载运行时配置并刷新模块级变量。"""
    global _cfg, _asr, FFMPEG_PATH
    global MAX_CHUNK_SEC, MAX_FILE_BYTES, ASR_PARALLEL_WORKERS
    global ASR_MAX_RETRIES, ASR_REQUEST_TIMEOUT_SEC
    global DEFAULT_ASR_MODEL, base_url, api_key

    _cfg = reload_config()
    _asr = _cfg["asr"]
    FFMPEG_PATH = _resolve_ffmpeg(_cfg["ffmpeg_path"])
    os.environ["FFMPEG_BINARY"] = FFMPEG_PATH
    MAX_CHUNK_SEC = float(_asr["max_chunk_sec"])
    MAX_FILE_BYTES = int(_asr["max_file_bytes"])
    ASR_PARALLEL_WORKERS = int(_asr["parallel_workers"])
    ASR_MAX_RETRIES = int(_asr["max_retries"])
    ASR_REQUEST_TIMEOUT_SEC = int(_asr["request_timeout_sec"])
    DEFAULT_ASR_MODEL = _asr["model"]
    base_url = _asr["base_url"]
    api_key = _asr["api_key"]
    refresh_vad_config()


def _emit(msg: str, *, progress: Callable[[str], None] | None = None) -> None:
    cb = progress or _progress_cb.get()
    if cb:
        cb(msg)


def video_to_wav(input_path: str, output_path: str, *, progress: Callable[[str], None] | None = None) -> str:
    """将视频/音频转换为 WAV 格式。"""
    from moviepy.audio.io.AudioFileClip import AudioFileClip

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    _emit(f"开始转换: {input_path.name} → {output_path.name}", progress=progress)

    audio = AudioFileClip(str(input_path))
    _emit(
        f"音频信息: 时长={audio.duration:.2f}秒, 采样率={audio.fps}Hz, 声道={audio.nchannels}",
        progress=progress,
    )

    audio.write_audiofile(
        str(output_path),
        fps=audio.fps,
        nbytes=2,
        codec="pcm_s16le",
    )
    audio.close()
    _emit("音频转换完成", progress=progress)

    return str(output_path)


def _needs_splitting(wav_path: str | Path) -> bool:
    path = Path(wav_path)
    duration = get_wav_duration(path)
    size = path.stat().st_size
    return duration > MAX_CHUNK_SEC or size > MAX_FILE_BYTES


async def voice_to_text(
    file_path: str,
    model: str | None = None,
    chunk_index: int | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """调用硅基流动 API 将音频转为文字，含重试与错误日志。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    model = model or DEFAULT_ASR_MODEL

    if not base_url or not api_key:
        raise ValueError("请在「媒体工具 · 工具配置」中设置 asr.base_url 和 asr.api_key")
    if not model:
        raise ValueError("请在「媒体工具 · 工具配置」中设置 asr.model")

    url = f"{base_url}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    file_name = os.path.basename(file_path)
    label = f"段 {chunk_index}" if chunk_index is not None else file_name

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=ASR_REQUEST_TIMEOUT_SEC)

    last_error: Exception | None = None
    try:
        for attempt in range(ASR_MAX_RETRIES):
            try:
                with open(file_path, "rb") as audio_file:
                    files = {
                        "file": (file_name, audio_file),
                        "model": (None, model),
                    }
                    response = await client.post(url, headers=headers, files=files)
                    if not response.is_success:
                        _emit(
                            f"[{label}] ASR 失败 (HTTP {response.status_code}): {response.text[:500]}"
                        )
                    response.raise_for_status()
                    return response.json().get("text", "")
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else 0
                if attempt < ASR_MAX_RETRIES - 1 and status >= 500:
                    wait = 2**attempt
                    _emit(
                        f"[{label}] 服务端错误，{wait}s 后重试 ({attempt + 1}/{ASR_MAX_RETRIES})..."
                    )
                    await asyncio.sleep(wait)
                    continue
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < ASR_MAX_RETRIES - 1:
                    wait = 2**attempt
                    _emit(
                        f"[{label}] 请求异常，{wait}s 后重试 ({attempt + 1}/{ASR_MAX_RETRIES})..."
                    )
                    await asyncio.sleep(wait)
                    continue
                raise
    finally:
        if owns_client and client is not None:
            await client.aclose()

    raise RuntimeError(f"[{label}] ASR 重试耗尽") from last_error


async def _transcribe_one_chunk(
    idx: int,
    path: str,
    boundaries: list[float],
    model: str | None,
    total: int,
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
) -> tuple[int, str]:
    async with semaphore:
        text = await voice_to_text(path, model, idx + 1, client=client)
        start = format_timestamp(boundaries[idx])
        end = format_timestamp(boundaries[idx + 1])
        _emit(f"[段 {idx + 1}/{total}] 转写完成 ({start}–{end})")
        return idx, text


async def _transcribe_chunks_parallel(
    chunk_paths: list[str],
    boundaries: list[float],
    model: str | None,
    max_workers: int,
) -> list[str]:
    """并行转写各片段，返回与 chunk_paths 顺序一致的结果。"""
    total = len(chunk_paths)
    semaphore = asyncio.Semaphore(max_workers)
    async with httpx.AsyncClient(timeout=ASR_REQUEST_TIMEOUT_SEC) as client:
        tasks = [
            _transcribe_one_chunk(i, path, boundaries, model, total, semaphore, client)
            for i, path in enumerate(chunk_paths)
        ]
        results = await asyncio.gather(*tasks)

    ordered: list[str | None] = [None] * len(chunk_paths)
    for idx, text in results:
        ordered[idx] = text
    return [text or "" for text in ordered]


async def long_audio_to_text(
    wav_path: str,
    model: str | None = None,
    max_workers: int | None = None,
) -> str:
    """长音频 VAD 切分后并行 ASR，短音频直接转写。"""
    wav_path_obj = Path(wav_path)
    duration = get_wav_duration(wav_path_obj)
    size_mb = wav_path_obj.stat().st_size / (1024 * 1024)

    if not _needs_splitting(wav_path):
        _emit(f"音频时长 {duration:.1f}s / {size_mb:.1f}MB，无需切分")
        return await voice_to_text(wav_path, model=model)

    max_chunk_sec = compute_max_chunk_sec(
        duration, wav_path_obj.stat().st_size, MAX_CHUNK_SEC, MAX_FILE_BYTES
    )
    _emit(
        f"音频时长 {duration:.1f}s / {size_mb:.1f}MB，开始 VAD 切分..."
        f"（单段上限 {max_chunk_sec / 60:.1f}min）"
    )
    silences = detect_silences(wav_path)
    _emit(f"检测到 {len(silences)} 个静音区间")

    boundaries = find_chunk_boundaries(duration, silences, max_chunk_sec=max_chunk_sec)
    chunk_count = len(boundaries) - 1
    chunk_durations = [boundaries[i + 1] - boundaries[i] for i in range(chunk_count)]
    _emit(
        f"切分为 {chunk_count} 段，各段时长: "
        + ", ".join(f"{d / 60:.1f}min" for d in chunk_durations)
    )

    chunk_dir = Path(tempfile.mkdtemp(prefix="vad_chunks_"))
    try:
        chunk_paths = split_wav_at_boundaries(wav_path, boundaries, chunk_dir)
        workers = max_workers or ASR_PARALLEL_WORKERS
        _emit(f"开始并行语音识别（{workers} 并发）...")
        texts = await _transcribe_chunks_parallel(chunk_paths, boundaries, model, workers)
        return "\n".join(texts)
    finally:
        shutil.rmtree(chunk_dir, ignore_errors=True)


async def _media_to_text(
    media_path: str,
    allowed_suffixes: set[str],
    type_label: str,
    model: str | None = None,
    max_workers: int | None = None,
    *,
    progress: Callable[[str], None] | None = None,
    strict_ext: bool = True,
) -> str:
    """通用转写入口：音视频文件 → WAV → 归一化 → VAD 切分并行 ASR。

    strict_ext=True 时扩展名必须在 allowed_suffixes 内，否则报错；
    strict_ext=False 时扩展名仅作提示，实际格式交由 ffmpeg/moviepy 内容探测
    （用于上传/直链保存后扩展名不可靠的场景）。
    """
    media_path_obj = Path(media_path)
    if not media_path_obj.exists():
        raise FileNotFoundError(f"文件不存在: {media_path_obj}")
    if strict_ext and media_path_obj.suffix.lower() not in allowed_suffixes:
        supported = "、".join(sorted(allowed_suffixes))
        raise ValueError(f"仅支持 {supported} 格式: {media_path_obj}")

    token = _progress_cb.set(progress) if progress else None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    normalized_path: str | None = None
    try:
        await asyncio.to_thread(video_to_wav, str(media_path_obj), wav_path, progress=progress)
        _emit("归一化音频: 16kHz 单声道...", progress=progress)
        normalized_path = await asyncio.to_thread(normalize_wav_for_asr, wav_path)
        _emit("开始语音识别...", progress=progress)
        return await long_audio_to_text(normalized_path, model=model, max_workers=max_workers)
    finally:
        Path(wav_path).unlink(missing_ok=True)
        if normalized_path:
            Path(normalized_path).unlink(missing_ok=True)
        if token is not None:
            _progress_cb.reset(token)


async def mp4_to_text(
    mp4_path: str,
    model: str | None = None,
    max_workers: int | None = None,
    *,
    progress: Callable[[str], None] | None = None,
) -> str:
    """输入 MP4 路径，输出识别文字。"""
    return await _media_to_text(
        mp4_path,
        {".mp4"},
        "MP4 视频",
        model=model,
        max_workers=max_workers,
        progress=progress,
    )


async def audio_to_text(
    audio_path: str,
    model: str | None = None,
    max_workers: int | None = None,
    *,
    progress: Callable[[str], None] | None = None,
) -> str:
    """输入音频文件路径（MP3/WAV/M4A/FLAC/AAC/OGG 等），输出识别文字。

    扩展名仅作提示，实际格式由 ffmpeg/moviepy 探测，兼容临时文件无正确后缀的场景。
    """
    return await _media_to_text(
        audio_path,
        SUPPORTED_AUDIO_SUFFIXES,
        "音频",
        model=model,
        max_workers=max_workers,
        progress=progress,
        strict_ext=False,
    )
