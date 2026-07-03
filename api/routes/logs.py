from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.logs import (
    delete_log,
    delete_logs_by_app,
    delete_logs_by_session,
    list_log_apps,
    list_log_sessions,
    query_logs,
)

router = APIRouter(tags=["logs"])


@router.get("/logs")
async def get_logs(
    path: str | None = Query(default=None),
    model: str | None = Query(default=None),
    client_ip: str | None = Query(default=None),
    app_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    order_by: str = Query(default="created_at"),
    order_dir: str = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items, total = await query_logs(
        session,
        path=path,
        model=model,
        client_ip=client_ip,
        app_id=app_id,
        session_id=session_id,
        start_time=start_time,
        end_time=end_time,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
        offset=offset,
    )
    return JSONResponse(content={"items": items, "total": total, "limit": limit, "offset": offset})


@router.get("/logs/apps")
async def get_log_apps(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items, total = await list_log_apps(session, limit=limit, offset=offset)
    return JSONResponse(content={"items": items, "total": total, "limit": limit, "offset": offset})


@router.get("/logs/sessions")
async def get_log_sessions(
    app_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if not app_id or not str(app_id).strip():
        raise HTTPException(status_code=422, detail="app_id is required")
    try:
        items, total = await list_log_sessions(
            session, app_id=str(app_id).strip(), limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(content={"items": items, "total": total, "limit": limit, "offset": offset})


@router.delete("/logs/apps/{app_id}")
async def remove_logs_by_app(
    app_id: str,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        deleted_count = await delete_logs_by_app(session, app_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="app not found")
    return JSONResponse(content={"ok": True, "app_id": str(app_id).strip(), "deleted_count": deleted_count})


@router.delete("/logs/sessions")
async def remove_logs_by_session(
    app_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if not app_id or not str(app_id).strip():
        raise HTTPException(status_code=422, detail="app_id is required")
    if not session_id or not str(session_id).strip():
        raise HTTPException(status_code=422, detail="session_id is required")
    aid = str(app_id).strip()
    sid = str(session_id).strip()
    try:
        deleted_count = await delete_logs_by_session(session, aid, sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="session not found")
    return JSONResponse(content={"ok": True, "app_id": aid, "session_id": sid, "deleted_count": deleted_count})


@router.delete("/logs/{log_id}")
async def remove_log(
    log_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    deleted = await delete_log(session, log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="log not found")
    return JSONResponse(content={"ok": True, "deleted_id": log_id})
