from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.bookmarks import (
    create_bookmark,
    delete_bookmark,
    get_bookmark_detail,
    get_top5,
    list_bookmarks,
    record_access,
    set_bookmark_tags,
    update_bookmark,
)
from db.engine import get_session
from tools.bookmarks.schemas import (
    CreateBookmarkRequest,
    FetchMetadataRequest,
    SetBookmarkTagsRequest,
    UpdateBookmarkRequest,
)
from tools.bookmarks.services.metadata_fetcher import fetch_page_metadata

router = APIRouter(prefix="/bookmarks/admin", tags=["bookmarks-admin"])


def _http_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _http_lookup(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/bookmarks")
async def get_bookmarks(
    q: str | None = None,
    group_id: int | None = None,
    tag_ids: str | None = None,
    pinned_only: bool = False,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    ids: list[int] | None = None
    if tag_ids:
        try:
            ids = [int(x) for x in tag_ids.split(",") if x.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="tag_ids 格式无效") from exc
    items = await list_bookmarks(
        session,
        q=q,
        group_id=group_id,
        tag_ids=ids,
        pinned_only=pinned_only,
    )
    return JSONResponse(content={"items": items})


@router.get("/bookmarks/top5")
async def get_top5_endpoint(
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items = await get_top5(session)
    return JSONResponse(content={"items": items})


@router.get("/bookmarks/{bookmark_id}")
async def get_bookmark(
    bookmark_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    detail = await get_bookmark_detail(session, bookmark_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="书签不存在")
    return JSONResponse(content=detail)


@router.post("/bookmarks")
async def post_bookmark(
    body: CreateBookmarkRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await create_bookmark(
            session,
            url=body.url,
            title=body.title,
            favicon_url=body.favicon_url,
            group_id=body.group_id,
        )
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.post("/bookmarks/fetch-metadata")
async def fetch_metadata(
    body: FetchMetadataRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    result = await fetch_page_metadata(body.url)
    return JSONResponse(content=result)


@router.post("/bookmarks/{bookmark_id}")
@router.put("/bookmarks/{bookmark_id}")
async def update_bookmark_endpoint(
    bookmark_id: int,
    body: UpdateBookmarkRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await update_bookmark(
            session,
            bookmark_id,
            title=body.title,
            favicon_url=body.favicon_url,
            group_id=body.group_id,
            pinned=body.pinned,
        )
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark_endpoint(
    bookmark_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await delete_bookmark(session, bookmark_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content={"ok": True})


@router.post("/bookmarks/{bookmark_id}/access")
async def record_access_endpoint(
    bookmark_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await record_access(session, bookmark_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content=item)


@router.post("/bookmarks/{bookmark_id}/tags")
@router.put("/bookmarks/{bookmark_id}/tags")
async def set_tags_endpoint(
    bookmark_id: int,
    body: SetBookmarkTagsRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await set_bookmark_tags(session, bookmark_id, body.tag_ids)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)
