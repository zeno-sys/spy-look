from __future__ import annotations

from datetime import datetime

from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from db.models import SpyLookReadLater


async def list_items(
    session: AsyncSession,
    *,
    status: str | None = None,
    q: str | None = None,
) -> list[dict]:
    stmt: SelectOfScalar = select(SpyLookReadLater).order_by(
        SpyLookReadLater.created_at.desc()
    )
    if status:
        stmt = stmt.where(SpyLookReadLater.status == status)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            SpyLookReadLater.title.like(pattern) | SpyLookReadLater.url.like(pattern)
        )
    result = await session.exec(stmt)
    return [_item_row(r) for r in result.all()]


async def get_item(session: AsyncSession, item_id: int) -> dict | None:
    row = await session.get(SpyLookReadLater, item_id)
    return _item_row(row) if row else None


async def create_item(
    session: AsyncSession,
    url: str,
    title: str = "",
    summary: str = "",
    bookmark_id: int | None = None,
) -> dict:
    existing = await _find_by_url(session, url)
    if existing:
        raise ValueError(f"URL 已存在稍后阅读列表: {url}")
    row = SpyLookReadLater(
        url=url,
        title=title,
        summary=summary,
        status="pending",
        bookmark_id=bookmark_id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _item_row(row)


async def update_item(
    session: AsyncSession,
    item_id: int,
    *,
    title: str | None = None,
    summary: str | None = None,
    status: str | None = None,
    bookmark_id: int | None | str = None,
) -> dict:
    row = await session.get(SpyLookReadLater, item_id)
    if not row:
        raise LookupError(f"稍后阅读项不存在: {item_id}")
    if title is not None:
        row.title = title
    if summary is not None:
        row.summary = summary
    if status is not None:
        if status not in ("pending", "read", "archived"):
            raise ValueError(f"无效的状态: {status}")
        row.status = status
    if bookmark_id != _UNSET:
        row.bookmark_id = bookmark_id
    row.updated_at = datetime.utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _item_row(row)


async def delete_item(session: AsyncSession, item_id: int) -> None:
    row = await session.get(SpyLookReadLater, item_id)
    if not row:
        raise LookupError(f"稍后阅读项不存在: {item_id}")
    await session.delete(row)
    await session.commit()


async def _find_by_url(session: AsyncSession, url: str) -> SpyLookReadLater | None:
    stmt = select(SpyLookReadLater).where(SpyLookReadLater.url == url)
    result = await session.exec(stmt)
    return result.first()


def _item_row(row: SpyLookReadLater) -> dict:
    return {
        "id": row.id,
        "url": row.url,
        "title": row.title,
        "summary": row.summary,
        "status": row.status,
        "bookmark_id": row.bookmark_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


_UNSET = object()
