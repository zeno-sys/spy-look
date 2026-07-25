from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile

from tools.image_tools.schemas import FormulaResponse, LayoutResponse, OcrResponse
from tools.image_tools.services.formula import (
    expected_models_dir as formula_models_dir,
    run_formula_on_bytes,
)
from tools.image_tools.services.layout import (
    expected_models_dir as layout_models_dir,
    run_layout_on_bytes,
)
from tools.image_tools.services.ocr import expected_models_dir as ocr_models_dir
from tools.image_tools.services.ocr import run_ocr_on_bytes

router = APIRouter(prefix="/image-tools/admin", tags=["image-tools-admin"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


async def _read_image_upload(request: Request) -> bytes:
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in content_type:
        raise HTTPException(
            status_code=400,
            detail="请使用 multipart/form-data 上传 file 字段（图片）",
        )

    form = await request.form()
    upload = form.get("file")
    if upload is None or not isinstance(upload, UploadFile):
        raise HTTPException(status_code=400, detail="请上传 file 字段（图片）")

    filename = upload.filename or "image"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，仅支持: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    raw = await upload.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"上传文件超过大小上限 ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    return raw


@router.post("/ocr", response_model=OcrResponse)
async def image_ocr(request: Request) -> OcrResponse:
    raw = await _read_image_upload(request)
    try:
        payload = await asyncio.to_thread(run_ocr_on_bytes, raw)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc}（期望目录: {ocr_models_dir()}）",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR 失败: {exc}") from exc

    return OcrResponse.model_validate(payload)


@router.post("/formula", response_model=FormulaResponse)
async def image_formula(request: Request) -> FormulaResponse:
    raw = await _read_image_upload(request)
    try:
        payload = await asyncio.to_thread(run_formula_on_bytes, raw)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc}（期望目录: {formula_models_dir()}）",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"公式识别失败: {exc}") from exc

    return FormulaResponse.model_validate(payload)


@router.post("/layout", response_model=LayoutResponse)
async def image_layout(request: Request) -> LayoutResponse:
    raw = await _read_image_upload(request)
    try:
        payload = await asyncio.to_thread(run_layout_on_bytes, raw)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc}（期望目录: {layout_models_dir()}）",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"版面识别失败: {exc}") from exc

    return LayoutResponse.model_validate(payload)
