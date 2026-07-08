from __future__ import annotations

import copy
import json
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.logs import (
    delete_log,
    delete_logs_by_app,
    delete_logs_by_session,
    get_apps_dashboard_stats,
    get_log,
    list_log_apps,
    list_log_models,
    list_log_sessions,
    query_logs,
)
from db.upstreams import get_upstream_runtime
from tools.gateway.schemas import LogReplayRequest
from tools.gateway.services.upstream_client import UpstreamClient, upstream_runtime_from_row

router = APIRouter(prefix="/gateway/logs", tags=["gateway-logs"])


@router.get("")
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


@router.get("/models")
async def get_log_models(
    app_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if not app_id or not str(app_id).strip():
        raise HTTPException(status_code=422, detail="app_id is required")
    if not session_id or not str(session_id).strip():
        raise HTTPException(status_code=422, detail="session_id is required")
    try:
        models = await list_log_models(
            session,
            app_id=str(app_id).strip(),
            session_id=str(session_id).strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(content={"items": models})


@router.get("/apps/stats")
async def get_log_apps_stats(
    top_n: int = Query(default=10, ge=1, le=50),
    timeline_days: int = Query(default=14, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    stats = await get_apps_dashboard_stats(session, top_n=top_n, timeline_days=timeline_days)
    return JSONResponse(content=stats)


@router.get("/apps")
async def get_log_apps(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    items, total = await list_log_apps(session, limit=limit, offset=offset)
    return JSONResponse(content={"items": items, "total": total, "limit": limit, "offset": offset})


@router.get("/sessions")
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


@router.delete("/apps/{app_id}")
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


@router.delete("/sessions")
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


def _parse_request_body(raw: Any) -> dict[str, Any]:
    if raw is None:
        raise HTTPException(status_code=400, detail="log has no request body")
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise HTTPException(status_code=400, detail="log has no request body")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"invalid request body JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="request body must be a JSON object")
        return parsed
    raise HTTPException(status_code=400, detail="request body must be a JSON object")


@router.post("/{log_id}/replay")
async def replay_log(
    log_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        raw = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from None
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    try:
        body = LogReplayRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from None

    log = await get_log(session, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="log not found")

    row = await get_upstream_runtime(session, body.upstream_id)
    if not row:
        raise HTTPException(status_code=400, detail="upstream not found")
    if not row.get("enabled"):
        raise HTTPException(status_code=400, detail="upstream is disabled")

    cfg = upstream_runtime_from_row(row)
    if not cfg:
        raise HTTPException(status_code=400, detail="incomplete upstream configuration")

    payload = _parse_request_body(log.get("request_body"))
    payload["model"] = str(body.model).strip()
    payload["stream"] = False

    client = UpstreamClient(cfg)
    t0 = time.perf_counter()
    try:
        resp = await client.chat_completions(payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="upstream timeout") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await client.close()

    latency_ms = int((time.perf_counter() - t0) * 1000)
    try:
        response_body: Any = resp.json()
    except ValueError:
        response_body = {"raw": (resp.text or "")[:8000]}

    return JSONResponse(content={
        "ok": not resp.is_error,
        "log_id": log_id,
        "upstream_id": body.upstream_id,
        "model": payload["model"],
        "status_code": resp.status_code,
        "latency_ms": latency_ms,
        "response_body": response_body,
    })


@router.delete("/{log_id}")
async def remove_log(
    log_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    deleted = await delete_log(session, log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="log not found")
    return JSONResponse(content={"ok": True, "deleted_id": log_id})
