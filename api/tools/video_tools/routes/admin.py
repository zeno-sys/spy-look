from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile

from db.upstreams import mask_api_key
from tools.video_tools.schemas import VideoToolsConfig, VideoToolsConfigPatch, VoiceToTextUrlRequest

_SERVICES_DIR = Path(__file__).resolve().parent.parent / "services"
if str(_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR))

from config_loader import load_config, reload_config, save_config  # noqa: E402
import voice_to_text  # noqa: E402

router = APIRouter(prefix="/video-tools/admin", tags=["video-tools-admin"])

# 源视频下载上限（与 ASR 单段体积限制分开，允许更长视频）
MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def _mask_config(data: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(data)
    asr = dict(cfg.get("asr") or {})
    if asr.get("api_key"):
        asr["api_key"] = mask_api_key(str(asr["api_key"]))
    cfg["asr"] = asr
    return cfg


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            for nk, nv in value.items():
                if nv is None:
                    continue
                if nk == "api_key" and isinstance(nv, str) and not nv.strip():
                    continue
                nested[nk] = nv
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _download_headers(url: str) -> dict[str, str]:
    headers = dict(_BROWSER_HEADERS)
    host = urlparse(url).netloc.lower()
    if "bilivideo.com" in host or "bilibili.com" in host:
        headers["Referer"] = "https://www.bilibili.com/"
    return headers


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return _mask_config(load_config())


@router.patch("/config")
async def patch_config(body: VideoToolsConfigPatch) -> dict[str, Any]:
    current = load_config()
    patch = body.model_dump(exclude_none=True)
    if body.asr is not None:
        asr_patch = body.asr.model_dump()
        if not (asr_patch.get("api_key") or "").strip():
            asr_patch.pop("api_key", None)
        patch["asr"] = asr_patch
    merged = _deep_merge(current, patch)
    try:
        VideoToolsConfig.model_validate(merged)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}") from exc
    save_config(merged)
    reload_config()
    voice_to_text.refresh_config()
    return _mask_config(merged)


async def _download_video_url(
    url: str,
    dest: Path,
    max_bytes: int,
    on_progress: Callable[[str], None] | None = None,
) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 http/https 视频链接")

    headers = _download_headers(url)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0),
        headers=headers,
    ) as client:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise ValueError(f"下载失败: HTTP {response.status_code}")

            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(
                    f"视频文件超过大小上限 ({int(content_length) / (1024 * 1024):.1f} MB > "
                    f"{max_bytes / (1024 * 1024):.0f} MB)"
                )

            total = 0
            last_report_mb = -1
            with dest.open("wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 256):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(
                            f"视频文件超过大小上限 ({max_bytes / (1024 * 1024):.0f} MB)"
                        )
                    f.write(chunk)
                    if on_progress:
                        mb = total // (1024 * 1024)
                        if mb > last_report_mb:
                            last_report_mb = mb
                            on_progress(f"正在下载视频... 已下载 {mb} MB")

    if on_progress:
        size_mb = dest.stat().st_size / (1024 * 1024)
        on_progress(f"视频下载完成 ({size_mb:.1f} MB)")


async def _save_upload_file(
    upload: UploadFile,
    dest: Path,
    on_progress: Callable[[str], None] | None = None,
) -> None:
    filename = (upload.filename or "").lower()
    if not filename.endswith(".mp4"):
        raise ValueError("仅支持 .mp4 文件")

    max_bytes = MAX_DOWNLOAD_BYTES
    total = 0
    if on_progress:
        on_progress(f"正在接收上传文件: {upload.filename}")

    with dest.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 256)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(
                    f"上传文件超过大小上限 ({max_bytes / (1024 * 1024):.0f} MB)"
                )
            f.write(chunk)

    if on_progress:
        size_mb = dest.stat().st_size / (1024 * 1024)
        on_progress(f"文件接收完成 ({size_mb:.1f} MB)")


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _parse_request_input(request: Request) -> tuple[UploadFile | None, str | None]:
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not isinstance(upload, UploadFile):
            raise HTTPException(status_code=400, detail="请上传 file 字段（.mp4）")
        return upload, None
    if "application/json" in content_type:
        body = VoiceToTextUrlRequest.model_validate(await request.json())
        url = body.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="url 不能为空")
        return None, url
    raise HTTPException(
        status_code=400,
        detail="请使用 multipart/form-data 上传文件或 application/json 提交 url",
    )


@router.post("/voice-to-text")
async def voice_to_text_stream(request: Request) -> StreamingResponse:
    upload, video_url = await _parse_request_input(request)

    async def event_stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_progress(message: str) -> None:
            loop.call_soon_threadsafe(
                queue.put_nowait, ("progress", {"message": message})
            )

        async def run_job() -> None:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            mp4_path = Path(tmp.name)
            tmp.close()
            try:
                if upload is not None:
                    await _save_upload_file(upload, mp4_path, on_progress)
                else:
                    await _download_video_url(
                        video_url or "",
                        mp4_path,
                        MAX_DOWNLOAD_BYTES,
                        on_progress,
                    )

                reload_config()
                voice_to_text.refresh_config()
                text = await voice_to_text.mp4_to_text(str(mp4_path), progress=on_progress)
                await queue.put(("done", {"text": text}))
            except Exception as exc:
                await queue.put(("error", {"detail": str(exc)}))
            finally:
                mp4_path.unlink(missing_ok=True)
                await queue.put(("__close__", {}))

        task = asyncio.create_task(run_job())
        try:
            while True:
                event, data = await queue.get()
                if event == "__close__":
                    break
                yield _sse_event(event, data)
                if event in ("done", "error"):
                    break
        finally:
            if not task.done():
                task.cancel()
                with asyncio.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")
