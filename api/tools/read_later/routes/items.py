from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.read_later import (
    create_item,
    delete_item,
    get_item,
    list_items,
    update_item,
)
from tools.bookmarks.services.metadata_fetcher import fetch_page_metadata
from tools.read_later.schemas import CreateItemRequest, UpdateItemRequest

router = APIRouter(prefix="/bookmarks/admin/read-later", tags=["read-later"])


def _http_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _http_lookup(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("")
async def get_items(
    status: str | None = Query(None),
    q: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items = await list_items(session, status=status, q=q)
    return JSONResponse(content={"items": items})


@router.get("/{item_id}")
async def get_item_endpoint(
    item_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    item = await get_item(session, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="稍后阅读项不存在")
    return JSONResponse(content=item)


@router.post("")
async def post_item(
    body: CreateItemRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    # Auto-fetch title if not provided
    title = body.title
    if not title:
        meta = await fetch_page_metadata(body.url)
        title = meta.get("title", "")
    try:
        item = await create_item(
            session,
            url=body.url,
            title=title,
            summary=body.summary,
            bookmark_id=body.bookmark_id,
        )
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.post("/{item_id}")
@router.put("/{item_id}")
async def update_item_endpoint(
    item_id: int,
    body: UpdateItemRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await update_item(
            session,
            item_id,
            title=body.title,
            summary=body.summary,
            status=body.status,
            bookmark_id=body.bookmark_id,
        )
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.delete("/{item_id}")
async def delete_item_endpoint(
    item_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await delete_item(session, item_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content={"ok": True})
