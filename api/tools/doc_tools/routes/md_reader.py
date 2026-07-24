from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db import md_documents as md_docs
from tools.doc_tools.schemas import MdDocumentCreateRequest, MdDocumentUpdateRequest

router = APIRouter(tags=["doc-tools-md-reader"])


@router.get("/documents")
async def list_md_documents(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    items = await md_docs.list_documents(session)
    return JSONResponse(content={"items": items})


@router.get("/recent")
async def list_md_recent(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    items = await md_docs.list_recent_opens(session)
    return JSONResponse(content={"items": items})


@router.post("/documents")
async def create_md_document(
    body: MdDocumentCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        doc = await md_docs.create_document(session, title=body.title, content=body.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(content=doc)


@router.post("/documents/upload")
async def upload_md_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    filename = file.filename or "document.md"
    lower = filename.lower()
    if not (lower.endswith(".md") or lower.endswith(".markdown") or lower.endswith(".txt")):
        raise HTTPException(status_code=400, detail="仅支持 .md / .markdown / .txt 文件")
    raw = await file.read()
    if len(raw) > md_docs.MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"上传文件超过大小上限 ({md_docs.MAX_DOCUMENT_BYTES // (1024 * 1024)} MB)",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="文件需为 UTF-8 编码") from exc
    try:
        doc = await md_docs.create_document(session, title=filename, content=text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(content=doc)


@router.get("/documents/{document_id}")
async def get_md_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    doc = await md_docs.get_document(session, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    await md_docs.touch_recent_open(session, document_id)
    return JSONResponse(content=doc)


@router.api_route("/documents/{document_id}", methods=["PATCH", "POST"])
async def update_md_document(
    document_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    # POST used as PATCH override (see ui apiPatch)
    if request.method == "POST":
        override = (request.headers.get("X-HTTP-Method-Override") or "").upper()
        if override and override != "PATCH":
            raise HTTPException(status_code=405, detail="Method not allowed")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无效 JSON") from exc
    body = MdDocumentUpdateRequest.model_validate(payload)
    if body.title is None and body.content is None:
        raise HTTPException(status_code=400, detail="请提供 title 或 content")
    try:
        doc = await md_docs.update_document(
            session,
            document_id,
            title=body.title,
            content=body.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return JSONResponse(content=doc)


@router.delete("/documents/{document_id}")
async def delete_md_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    ok = await md_docs.delete_document(session, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return JSONResponse(content={"ok": True, "deleted_id": document_id})


@router.post("/documents/{document_id}/images")
async def upload_md_document_image(
    document_id: int,
    file: UploadFile = File(...),
    content_type: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    raw = await file.read()
    ctype = (content_type or file.content_type or "application/octet-stream").strip()
    try:
        image = await md_docs.create_document_image(
            session,
            document_id,
            data=raw,
            content_type=ctype,
            filename=file.filename,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="文档不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(content=image)


@router.get("/documents/{document_id}/images/{image_id}")
async def get_md_document_image(
    document_id: int,
    image_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await md_docs.get_document_image(session, document_id, image_id)
    if row is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    return Response(
        content=row.data,
        media_type=row.content_type or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=86400"},
    )
