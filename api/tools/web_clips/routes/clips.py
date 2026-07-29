from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.web_clips import (
    create_item,
    delete_item,
    get_item,
    list_items,
)
from tools.web_clips.schemas import ClipUrlRequest
from tools.web_clips.services.content_extractor import extract_content

router = APIRouter(prefix="/bookmarks/admin/web-clips", tags=["web-clips"])


def _http_lookup(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("")
async def get_clips(
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items = await list_items(session, q=q, limit=limit, offset=offset)
    return JSONResponse(content={"items": items})


@router.get("/{clip_id}")
async def get_clip(
    clip_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    item = await get_item(session, clip_id)
    if not item:
        raise HTTPException(status_code=404, detail="剪藏不存在")
    return JSONResponse(content=item)


@router.post("")
async def create_clip(
    body: ClipUrlRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Fetch a URL, extract content, and save it as a clip."""
    result = await extract_content(body.url)
    item = await create_item(
        session,
        url=body.url,
        title=result.get("title", ""),
        content_md=result.get("content_md", ""),
        content_html=result.get("content_html", ""),
        bookmark_id=body.bookmark_id,
    )
    resp = dict(item)
    if result.get("error"):
        resp["extract_error"] = result["error"]
    return JSONResponse(content=resp)


@router.delete("/{clip_id}")
async def delete_clip(
    clip_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await delete_item(session, clip_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content={"ok": True})
