from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from config import LEGACY_UNKNOWN_APP_ID
from db.models import SpyLookLog


def _to_json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _like_contains(needle: str) -> str:
    esc = (
        str(needle)
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{esc}%"


def _normalize_datetime(value: str) -> str:
    text = value.strip().replace("T", " ")
    if len(text) == 16:
        return f"{text}:00"
    return text


def _normalize_order_by(value: str) -> str:
    allowed = {"created_at", "latency_ms", "status_code"}
    return value if value in allowed else "created_at"


async def log_event(session: AsyncSession, event: dict[str, Any]) -> None:
    log = SpyLookLog(
        path=event.get("path"),
        model=event.get("model"),
        upstream_model=event.get("upstream_model"),
        status_code=event.get("status_code"),
        latency_ms=event.get("latency_ms"),
        client_ip=event.get("client_ip"),
        input_tokens=event.get("input_tokens"),
        output_tokens=event.get("output_tokens"),
        total_tokens=event.get("total_tokens"),
        request_body=_to_json_text(event.get("request_body")),
        response_body=_to_json_text(event.get("response_body")),
        session_id=event.get("session_id") or "default",
        app_id=event.get("app_id") or LEGACY_UNKNOWN_APP_ID,
    )
    session.add(log)
    await session.commit()


async def query_logs(
    session: AsyncSession,
    *,
    path: str | None = None,
    model: str | None = None,
    client_ip: str | None = None,
    app_id: str | None = None,
    session_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    base = select(SpyLookLog)

    if path is not None and str(path).strip():
        base = base.where(col(SpyLookLog.path).like(_like_contains(str(path).strip()), escape="\\"))
    if model:
        base = base.where(SpyLookLog.model == model)
    if client_ip:
        base = base.where(SpyLookLog.client_ip == client_ip)
    if app_id:
        base = base.where(SpyLookLog.app_id == app_id)
    if session_id:
        base = base.where(SpyLookLog.session_id == session_id)
    if start_time:
        base = base.where(SpyLookLog.created_at >= _normalize_datetime(start_time))
    if end_time:
        base = base.where(SpyLookLog.created_at <= _normalize_datetime(end_time))

    count_stmt = select(func.count()).select_from(base.subquery())
    count_result = await session.execute(count_stmt)
    total = count_result.scalars().one()

    sort_column = getattr(SpyLookLog, _normalize_order_by(order_by), SpyLookLog.created_at)
    stmt = base.order_by(sort_column.desc() if order_dir.lower() == "desc" else sort_column.asc())
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    items = [row.model_dump(mode='json') for row in rows]

    # QUICK_CHECK: Verify total is integer, not a Row object
    if not isinstance(total, int):
        total = int(total)
    return items, total


async def list_log_models(
    session: AsyncSession,
    *,
    app_id: str,
    session_id: str,
) -> list[str]:
    aid = str(app_id or "").strip()
    sid = str(session_id or "").strip()
    if not aid:
        raise ValueError("app_id is required")
    if not sid:
        raise ValueError("session_id is required")

    stmt = (
        select(SpyLookLog.model)
        .where(
            SpyLookLog.app_id == aid,
            SpyLookLog.session_id == sid,
            SpyLookLog.model.isnot(None),
            SpyLookLog.model != "",
        )
        .distinct()
        .order_by(SpyLookLog.model.asc())
    )
    result = await session.execute(stmt)
    return [str(row[0]) for row in result.all() if row[0]]


async def get_log(session: AsyncSession, log_id: int) -> dict[str, Any] | None:
    log = await session.get(SpyLookLog, log_id)
    if not log:
        return None
    return log.model_dump(mode="json")


async def delete_log(session: AsyncSession, log_id: int) -> bool:
    log = await session.get(SpyLookLog, log_id)
    if not log:
        return False
    await session.delete(log)
    await session.commit()
    return True


async def delete_logs_by_app(session: AsyncSession, app_id: str) -> int:
    aid = str(app_id or "").strip()
    if not aid:
        raise ValueError("app_id is required")
    stmt = delete(SpyLookLog).where(SpyLookLog.app_id == aid)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def delete_logs_by_session(session: AsyncSession, app_id: str, session_id: str) -> int:
    aid = str(app_id or "").strip()
    sid = str(session_id or "").strip()
    if not aid:
        raise ValueError("app_id is required")
    if not sid:
        raise ValueError("session_id is required")
    stmt = delete(SpyLookLog).where(SpyLookLog.app_id == aid, SpyLookLog.session_id == sid)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def list_log_apps(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    count_stmt = select(func.count(func.distinct(SpyLookLog.app_id)))
    count_result = await session.execute(count_stmt)
    total = count_result.scalars().one()

    last_cte = func.max(SpyLookLog.created_at).label("last_created_at")

    data_stmt = (
        select(
            SpyLookLog.app_id,
            func.count().label("log_count"),
            func.min(SpyLookLog.created_at).label("first_created_at"),
            last_cte,
            func.coalesce(func.sum(SpyLookLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(SpyLookLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(SpyLookLog.total_tokens), 0).label("total_total_tokens"),
        )
        .group_by(SpyLookLog.app_id)
        .order_by(last_cte.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(data_stmt)
    rows = result.all()
    items = []
    for row in rows:
        items.append({
            "app_id": row[0],
            "log_count": row[1],
            "first_created_at": str(row[2]) if row[2] else None,
            "last_created_at": str(row[3]) if row[3] else None,
            "total_input_tokens": row[4],
            "total_output_tokens": row[5],
            "total_total_tokens": row[6],
        })
    return items, total


async def get_apps_dashboard_stats(
    session: AsyncSession,
    *,
    top_n: int = 10,
    timeline_days: int = 14,
) -> dict[str, Any]:
    summary_stmt = select(
        func.count(func.distinct(SpyLookLog.app_id)),
        func.count(),
        func.coalesce(func.sum(SpyLookLog.input_tokens), 0),
        func.coalesce(func.sum(SpyLookLog.output_tokens), 0),
        func.coalesce(func.sum(SpyLookLog.total_tokens), 0),
    )
    summary_row = (await session.execute(summary_stmt)).one()

    by_app_stmt = (
        select(
            SpyLookLog.app_id,
            func.count().label("log_count"),
            func.coalesce(func.sum(SpyLookLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(SpyLookLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(SpyLookLog.total_tokens), 0).label("total_total_tokens"),
        )
        .group_by(SpyLookLog.app_id)
        .order_by(func.count().desc())
        .limit(top_n)
    )
    by_app_rows = (await session.execute(by_app_stmt)).all()
    by_app = [
        {
            "app_id": row[0],
            "log_count": row[1],
            "total_input_tokens": row[2],
            "total_output_tokens": row[3],
            "total_total_tokens": row[4],
        }
        for row in by_app_rows
    ]

    from datetime import datetime, timedelta

    days = max(1, timeline_days)
    cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    timeline_stmt = (
        select(
            func.date(SpyLookLog.created_at).label("day"),
            func.count().label("log_count"),
            func.coalesce(func.sum(SpyLookLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(SpyLookLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(SpyLookLog.total_tokens), 0).label("total_total_tokens"),
        )
        .where(SpyLookLog.created_at >= cutoff)
        .group_by(func.date(SpyLookLog.created_at))
        .order_by(func.date(SpyLookLog.created_at))
    )
    timeline_rows = (await session.execute(timeline_stmt)).all()
    timeline_map = {
        str(row[0]): {
            "date": str(row[0]),
            "log_count": row[1],
            "total_input_tokens": row[2],
            "total_output_tokens": row[3],
            "total_total_tokens": row[4],
        }
        for row in timeline_rows
    }

    timeline: list[dict[str, Any]] = []
    for i in range(days):
        day = (cutoff + timedelta(days=i)).date().isoformat()
        timeline.append(timeline_map.get(day, {
            "date": day,
            "log_count": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_total_tokens": 0,
        }))

    return {
        "summary": {
            "app_count": int(summary_row[0] or 0),
            "log_count": int(summary_row[1] or 0),
            "total_input_tokens": int(summary_row[2] or 0),
            "total_output_tokens": int(summary_row[3] or 0),
            "total_total_tokens": int(summary_row[4] or 0),
        },
        "by_app": by_app,
        "timeline": timeline,
    }


async def list_log_sessions(
    session: AsyncSession, *, app_id: str, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    aid = str(app_id or "").strip()
    if not aid:
        raise ValueError("app_id is required")

    count_stmt = select(func.count(func.distinct(SpyLookLog.session_id))).where(SpyLookLog.app_id == aid)
    count_result = await session.execute(count_stmt)
    total = count_result.scalars().one()

    last_cte = func.max(SpyLookLog.created_at).label("last_created_at")

    data_stmt = (
        select(
            SpyLookLog.session_id,
            func.count().label("log_count"),
            func.min(SpyLookLog.created_at).label("first_created_at"),
            last_cte,
            func.coalesce(func.sum(SpyLookLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(SpyLookLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(SpyLookLog.total_tokens), 0).label("total_total_tokens"),
        )
        .where(SpyLookLog.app_id == aid)
        .group_by(SpyLookLog.session_id)
        .order_by(last_cte.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(data_stmt)
    rows = result.all()
    items = []
    for row in rows:
        items.append({
            "session_id": row[0],
            "log_count": row[1],
            "first_created_at": str(row[2]) if row[2] else None,
            "last_created_at": str(row[3]) if row[3] else None,
            "total_input_tokens": row[4],
            "total_output_tokens": row[5],
            "total_total_tokens": row[6],
        })
    return items, total
