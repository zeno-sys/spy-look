from __future__ import annotations

from datetime import datetime

from sqlmodel import select, desc
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from db.models import SpyLookWebClip


async def list_items(
    session: AsyncSession,
    *,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    stmt: SelectOfScalar = (
        select(SpyLookWebClip)
        .order_by(desc(SpyLookWebClip.fetched_at))
        .offset(offset)
        .limit(limit)
    )
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            SpyLookWebClip.title.like(pattern) | SpyLookWebClip.url.like(pattern)
        )
    result = await session.exec(stmt)
    return [_item_summary(r) for r in result.all()]


async def get_item(session: AsyncSession, item_id: int) -> dict | None:
    row = await session.get(SpyLookWebClip, item_id)
    return _item_full(row) if row else None


async def create_item(
    session: AsyncSession,
    url: str,
    title: str = "",
    content_md: str = "",
    content_html: str = "",
    bookmark_id: int | None = None,
) -> dict:
    row = SpyLookWebClip(
        url=url,
        title=title,
        content_md=content_md,
        content_html=content_html,
        bookmark_id=bookmark_id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _item_summary(row)


async def delete_item(session: AsyncSession, item_id: int) -> None:
    row = await session.get(SpyLookWebClip, item_id)
    if not row:
        raise LookupError(f"剪藏不存在: {item_id}")
    await session.delete(row)
    await session.commit()


def _item_summary(row: SpyLookWebClip) -> dict:
    return {
        "id": row.id,
        "url": row.url,
        "title": row.title,
        "bookmark_id": row.bookmark_id,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }


def _item_full(row: SpyLookWebClip) -> dict:
    return {
        "id": row.id,
        "url": row.url,
        "title": row.title,
        "content_md": row.content_md,
        "content_html": row.content_html,
        "bookmark_id": row.bookmark_id,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }
