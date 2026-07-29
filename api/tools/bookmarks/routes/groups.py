from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.bookmarks import (
    create_group,
    delete_group,
    list_groups,
    update_group,
)
from db.engine import get_session
from tools.bookmarks.schemas import CreateGroupRequest, UpdateGroupRequest

router = APIRouter(prefix="/bookmarks/admin", tags=["bookmarks-admin-groups"])


def _http_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _http_lookup(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/groups")
async def get_groups(
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items = await list_groups(session)
    return JSONResponse(content={"items": items})


@router.post("/groups")
async def post_group(
    body: CreateGroupRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await create_group(session, body.name, body.sort_order)
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.post("/groups/{group_id}")
@router.put("/groups/{group_id}")
async def update_group_endpoint(
    group_id: int,
    body: UpdateGroupRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await update_group(
            session,
            group_id,
            name=body.name,
            sort_order=body.sort_order,
        )
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.delete("/groups/{group_id}")
async def delete_group_endpoint(
    group_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await delete_group(session, group_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content={"ok": True})
