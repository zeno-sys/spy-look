"""使用 yt-dlp 解析并下载视频页面链接（B 站、YouTube 等）。"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from config_loader import load_config, reload_config

_cfg = load_config()
FFMPEG_PATH = _cfg["ffmpeg_path"]
_ytdlp = _cfg.get("ytdlp") or {}

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class _QuietLogger:
    """抑制 yt-dlp 向 stderr 输出 ERROR（失败时由上层统一抛错）。"""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


def refresh_config() -> None:
    """重新加载运行时配置。"""
    global _cfg, FFMPEG_PATH, _ytdlp

    _cfg = reload_config()
    FFMPEG_PATH = _cfg["ffmpeg_path"]
    _ytdlp = _cfg.get("ytdlp") or {}


def download_page_video(
    url: str,
    dest: Path,
    max_bytes: int,
    *,
    progress: Callable[[str], None] | None = None,
) -> None:
    """从视频页面链接下载并确保输出为 MP4。"""
    url = url.strip()
    if not url:
        raise ValueError("页面链接不能为空")

    temp_dir = Path(tempfile.mkdtemp(prefix="ytdlp_"))
    out_template = str(temp_dir / "video.%(ext)s")
    last_report_pct = -1
    last_report_mb = -1

    def _emit(msg: str) -> None:
        if progress:
            progress(msg)

    def hook(d: dict) -> None:
        nonlocal last_report_pct, last_report_mb
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = int(d.get("downloaded_bytes") or 0)
            if downloaded > max_bytes:
                raise ValueError(
                    f"视频文件超过大小上限 ({max_bytes / (1024 * 1024):.0f} MB)"
                )
            if total:
                pct = downloaded * 100 // int(total)
                if pct > last_report_pct:
                    last_report_pct = pct
                    _emit(f"正在下载视频... {pct}%")
            else:
                mb = downloaded // (1024 * 1024)
                if mb > last_report_mb:
                    last_report_mb = mb
                    _emit(f"正在下载视频... 已下载 {mb} MB")
        elif status == "finished":
            _emit("页面视频下载完成，正在整理文件...")

    ydl_opts: dict = {
        "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": max_bytes,
        "progress_hooks": [hook],
        "logger": _QuietLogger(),
        "http_headers": _build_http_headers(url),
    }

    cookies_file = str(_ytdlp.get("cookies_file") or "").strip()
    cookies_browser = str(_ytdlp.get("cookies_from_browser") or "").strip()
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file
    elif cookies_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)

    ffmpeg_dir = _get_ffmpeg_dir()
    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    _emit(f"正在解析页面链接: {url}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        if info is None:
            raise ValueError("无法解析该页面链接，请检查 URL 是否正确")
        title = info.get("title") or "未知标题"
        _emit(f"已识别: {title}")

        downloaded = _find_downloaded_file(temp_dir)
        if downloaded is None:
            raise ValueError("下载完成但未找到视频文件")

        size = downloaded.stat().st_size
        if size > max_bytes:
            raise ValueError(
                f"视频文件超过大小上限 ({size / (1024 * 1024):.1f} MB > "
                f"{max_bytes / (1024 * 1024):.0f} MB)"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        if downloaded.suffix.lower() == ".mp4":
            shutil.move(str(downloaded), str(dest))
        else:
            _emit(f"正在转换为 MP4（源格式 {downloaded.suffix}）...")
            _convert_to_mp4(downloaded, dest)

        size_mb = dest.stat().st_size / (1024 * 1024)
        _emit(f"视频准备完成 ({size_mb:.1f} MB)")
    except yt_dlp.utils.DownloadError as exc:
        raise ValueError(_format_download_error(url, exc)) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _is_bilibili_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(
        token in host
        for token in ("bilibili.com", "b23.tv", "bili2233.cn", "bilivideo.com")
    )


def _build_http_headers(url: str) -> dict[str, str]:
    headers = {"User-Agent": _BROWSER_USER_AGENT}
    if _is_bilibili_url(url):
        # B 站 API 会校验 Origin/Referer，缺失时返回 HTTP 412
        headers["Referer"] = url if url.startswith("http") else "https://www.bilibili.com/"
        headers["Origin"] = "https://www.bilibili.com"
    return headers


def _format_download_error(url: str, exc: Exception) -> str:
    message = str(exc)
    if _is_bilibili_url(url) and ("412" in message or "Precondition Failed" in message):
        hint = (
            "哔哩哔哩返回 HTTP 412（反爬校验）。"
            "请确认视频为公开可访问；若为会员/登录专享，可在工具配置中设置 "
            "ytdlp.cookies_from_browser（如 firefox）或 ytdlp.cookies_file。"
            "也可改用右侧备用在线解析，再通过「上传文件」或「视频链接」转写。"
        )
        return f"页面视频下载失败: {hint}"
    return f"页面视频下载失败: {message}"


def _find_downloaded_file(temp_dir: Path) -> Path | None:
    candidates = [
        p
        for p in temp_dir.iterdir()
        if p.is_file() and p.name.startswith("video.") and p.suffix.lower() != ".part"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_size)


def _convert_to_mp4(src: Path, dest: Path) -> None:
    command = [
        _get_ffmpeg_bin(),
        "-y",
        "-i",
        str(src),
        "-c",
        "copy",
        str(dest),
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = _safe_decode(result.stderr)
        raise RuntimeError(f"ffmpeg 转 MP4 失败: {stderr}")


def _get_ffmpeg_bin() -> str:
    ffmpeg_bin = Path(FFMPEG_PATH).expanduser()
    if ffmpeg_bin.exists():
        return str(ffmpeg_bin)
    return "ffmpeg"


def _get_ffmpeg_dir() -> str | None:
    ffmpeg_bin = Path(FFMPEG_PATH).expanduser()
    if ffmpeg_bin.exists():
        return str(ffmpeg_bin.parent)
    return None


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
