from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.algorithm_practice import (
    create_tag,
    delete_tag,
    list_tags,
    update_tag,
)
from db.engine import get_session
from tools.algorithm_practice.schemas import (
    CreateTagRequest,
    UpdateTagRequest,
)

router = APIRouter(prefix="/algorithm/admin", tags=["algorithm-tags"])


def _http_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _http_lookup(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/tags")
async def get_tags(
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items = await list_tags(session)
    return JSONResponse(content={"items": items})


@router.post("/tags")
async def post_tag(
    body: CreateTagRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await create_tag(session, body.name, body.color)
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.post("/tags/{tag_id}")
@router.put("/tags/{tag_id}")
async def update_tag_endpoint(
    tag_id: int,
    body: UpdateTagRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await update_tag(
            session,
            tag_id,
            name=body.name,
            color=body.color,
        )
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.delete("/tags/{tag_id}")
async def delete_tag_endpoint(
    tag_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await delete_tag(session, tag_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content={"ok": True})
