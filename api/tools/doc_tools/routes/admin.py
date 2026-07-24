from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.datastructures import UploadFile

from tools.doc_tools.schemas import (
    HeadingNumberingConfigSchema,
    HeadingStyleConfigSchema,
    MdHeadingNumberingRequest,
    MdToDocxRequest,
)
from tools.doc_tools.services.md_heading_numbering import (
    HeadingNumberingConfig,
    add_heading_numbering,
)
from tools.doc_tools.services.md_to_docx import DocTool, HeadingStyleConfig
from tools.doc_tools.routes.md_reader import router as md_reader_router

router = APIRouter(prefix="/doc-tools/admin", tags=["doc-tools-admin"])
router.include_router(md_reader_router)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _to_heading_config(
    schema: HeadingStyleConfigSchema | None,
) -> HeadingStyleConfig | None:
    if schema is None:
        return None
    return HeadingStyleConfig(
        numbering_enabled=schema.numbering_enabled,
        use_word_numbering=schema.use_word_numbering,
        max_numbering_level=schema.max_numbering_level,
        number_separator=schema.number_separator,
        number_suffix=schema.number_suffix,
        trailing_dot_on_top_level=schema.trailing_dot_on_top_level,
        font_name=schema.font_name,
        font_sizes_pt=tuple(schema.font_sizes_pt),
        space_before_pt=tuple(schema.space_before_pt),
        space_after_pt=tuple(schema.space_after_pt),
    )


def _run_md_to_docx(
    *,
    markdown_content: str,
    title: str,
    base_path: str | None = None,
    heading_config: HeadingStyleConfigSchema | None = None,
) -> Response:
    md = markdown_content.strip()
    if not md:
        raise HTTPException(status_code=400, detail="markdown 内容不能为空")

    doc_title = (title or "Document").strip() or "Document"
    tool = DocTool()
    blob: bytes | None = None
    filename = f"{doc_title.replace(' ', '_')}.docx"
    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    last_text = ""

    for msg in tool.invoke(
        {
            "markdown_content": md,
            "title": doc_title,
            "base_path": base_path,
            "heading_config": _to_heading_config(heading_config),
        }
    ):
        if msg.get("type") == "blob":
            blob = msg.get("data")
            meta = msg.get("meta") or {}
            filename = str(meta.get("filename") or filename)
            mime_type = str(meta.get("mime_type") or mime_type)
        elif msg.get("type") == "text":
            last_text = str(msg.get("content") or "")

    if blob is None:
        detail = last_text or "MD 转 DOCX 失败"
        raise HTTPException(status_code=400, detail=detail)

    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=blob,
        media_type=mime_type,
        headers={"Content-Disposition": disposition},
    )


async def _read_upload_markdown(upload: UploadFile) -> tuple[str, str]:
    filename = upload.filename or "document.md"
    lower = filename.lower()
    if not (lower.endswith(".md") or lower.endswith(".markdown") or lower.endswith(".txt")):
        raise HTTPException(status_code=400, detail="仅支持 .md / .markdown / .txt 文件")

    raw = await upload.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"上传文件超过大小上限 ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="文件需为 UTF-8 编码") from exc

    stem = Path(filename).stem or "Document"
    return text, stem


def _parse_heading_config_form(raw: object) -> HeadingStyleConfigSchema | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise HTTPException(status_code=400, detail="heading_config 需为 JSON 字符串")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"heading_config JSON 无效: {exc}") from exc
    try:
        return HeadingStyleConfigSchema.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"heading_config 无效: {exc}") from exc


def _to_heading_numbering_config(
    schema: HeadingNumberingConfigSchema | None,
) -> HeadingNumberingConfig | None:
    if schema is None:
        return None
    return HeadingNumberingConfig(
        start_level=schema.start_level,
        end_level=schema.end_level,
        level_separator=schema.level_separator,
        number_suffix=schema.number_suffix,
        heading_template=schema.heading_template,
        default_style=schema.default_style,
        level_styles=dict(schema.level_styles),
        strip_existing_number=schema.strip_existing_number,
    )


def _parse_numbering_config_form(raw: object) -> HeadingNumberingConfigSchema | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise HTTPException(status_code=400, detail="config 需为 JSON 字符串")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"config JSON 无效: {exc}") from exc
    try:
        return HeadingNumberingConfigSchema.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"config 无效: {exc}") from exc


def _run_md_heading_numbering(
    *,
    markdown_content: str,
    config: HeadingNumberingConfigSchema | None = None,
) -> dict[str, str]:
    md = markdown_content
    if not md.strip():
        raise HTTPException(status_code=400, detail="markdown 内容不能为空")
    try:
        result = add_heading_numbering(md, _to_heading_numbering_config(config))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"标题编号失败: {exc}") from exc
    return {"markdown_content": result}


@router.get("/md-to-docx/defaults")
async def md_to_docx_defaults() -> dict:
    """返回标题样式默认配置，供前端初始化表单。"""
    return HeadingStyleConfigSchema().model_dump()


@router.get("/md-heading-numbering/defaults")
async def md_heading_numbering_defaults() -> dict:
    """返回标题编号默认配置，供前端初始化表单。"""
    return HeadingNumberingConfigSchema().model_dump()


@router.post("/md-heading-numbering")
async def md_heading_numbering(request: Request) -> dict[str, str]:
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not isinstance(upload, UploadFile):
            raise HTTPException(status_code=400, detail="请上传 file 字段（.md）")
        config = _parse_numbering_config_form(form.get("config"))
        markdown_content, _ = await _read_upload_markdown(upload)
        return _run_md_heading_numbering(markdown_content=markdown_content, config=config)

    if "application/json" in content_type:
        body = MdHeadingNumberingRequest.model_validate(await request.json())
        return _run_md_heading_numbering(
            markdown_content=body.markdown_content,
            config=body.config,
        )

    raise HTTPException(
        status_code=400,
        detail="请使用 multipart/form-data 上传文件或 application/json 提交 markdown_content",
    )


@router.post("/md-to-docx")
async def md_to_docx(request: Request) -> Response:
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not isinstance(upload, UploadFile):
            raise HTTPException(status_code=400, detail="请上传 file 字段（.md）")

        title_raw = form.get("title")
        title = str(title_raw).strip() if isinstance(title_raw, str) and title_raw.strip() else ""
        heading_config = _parse_heading_config_form(form.get("heading_config"))
        markdown_content, default_title = await _read_upload_markdown(upload)
        return _run_md_to_docx(
            markdown_content=markdown_content,
            title=title or default_title,
            heading_config=heading_config,
        )

    if "application/json" in content_type:
        body = MdToDocxRequest.model_validate(await request.json())
        return _run_md_to_docx(
            markdown_content=body.markdown_content,
            title=body.title,
            base_path=body.base_path,
            heading_config=body.heading_config,
        )

    raise HTTPException(
        status_code=400,
        detail="请使用 multipart/form-data 上传文件或 application/json 提交 markdown_content",
    )
