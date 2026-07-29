from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse, urlunparse

from sqlalchemy import delete, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import (
    SpyLookBookmark,
    SpyLookBookmarkAccessLog,
    SpyLookBookmarkGroup,
    SpyLookBookmarkTag,
    SpyLookBookmarkTagLink,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def _tag_item(tag: SpyLookBookmarkTag) -> dict[str, Any]:
    return {"id": tag.id, "name": tag.name, "color": tag.color}


def _group_item(group: SpyLookBookmarkGroup, count: int = 0) -> dict[str, Any]:
    return {
        "id": group.id,
        "name": group.name,
        "sort_order": group.sort_order,
        "bookmark_count": count,
        "created_at": _iso(group.created_at),
        "updated_at": _iso(group.updated_at),
    }


def normalize_url(raw: str) -> str:
    """Normalize URL for unique constraint.

    - Lowercase scheme + host
    - Remove default ports (80 for http, 443 for https)
    - Strip trailing slash for non-root paths
    - Keep query and fragment as-is (dropped for simplicity in uniqueness check)
    - Do NOT normalize www vs non-www
    """
    raw = raw.strip()
    if not raw:
        return raw
    # Ensure scheme
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower() or "https"
    host = (parsed.hostname or "").lower()
    port = parsed.port
    # Remove default ports
    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    # Strip trailing slash for non-root paths; normalize root to empty
    path = parsed.path
    if not path or path == "/":
        path = ""
    else:
        path = path.rstrip("/")
    # Drop query and fragment for uniqueness — they rarely distinguish a "bookmark"
    normalized = urlunparse((scheme, netloc, path, "", "", ""))
    return normalized


# --------------------------------------------------------------------------- #
# Tags
# --------------------------------------------------------------------------- #

async def _tags_for_bookmark(
    session: AsyncSession, bookmark_id: int
) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookBookmarkTag)
        .join(
            SpyLookBookmarkTagLink,
            SpyLookBookmarkTagLink.tag_id == SpyLookBookmarkTag.id,
        )
        .where(SpyLookBookmarkTagLink.bookmark_id == bookmark_id)
        .order_by(SpyLookBookmarkTag.name)
    )
    result = await session.execute(stmt)
    return [_tag_item(t) for t in result.scalars().all()]


async def list_tags(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookBookmarkTag).order_by(SpyLookBookmarkTag.name)
    result = await session.execute(stmt)
    return [_tag_item(t) for t in result.scalars().all()]


async def create_tag(
    session: AsyncSession, name: str, color: str = "#64748b"
) -> dict[str, Any]:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("标签名不能为空")
    color = (color or "#64748b").strip() or "#64748b"
    existing = await session.execute(
        select(SpyLookBookmarkTag).where(SpyLookBookmarkTag.name == cleaned)
    )
    if existing.scalars().first() is not None:
        raise ValueError("标签已存在")
    tag = SpyLookBookmarkTag(name=cleaned, color=color)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return _tag_item(tag)


async def update_tag(
    session: AsyncSession,
    tag_id: int,
    *,
    name: str | None = None,
    color: str | None = None,
) -> dict[str, Any]:
    tag = await session.get(SpyLookBookmarkTag, tag_id)
    if tag is None:
        raise LookupError("标签不存在")
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("标签名不能为空")
        other = await session.execute(
            select(SpyLookBookmarkTag).where(
                SpyLookBookmarkTag.name == cleaned,
                SpyLookBookmarkTag.id != tag_id,
            )
        )
        if other.scalars().first() is not None:
            raise ValueError("标签名已存在")
        tag.name = cleaned
    if color is not None:
        tag.color = color.strip() or tag.color
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return _tag_item(tag)


async def delete_tag(session: AsyncSession, tag_id: int) -> None:
    tag = await session.get(SpyLookBookmarkTag, tag_id)
    if tag is None:
        raise LookupError("标签不存在")
    await session.execute(
        delete(SpyLookBookmarkTagLink).where(SpyLookBookmarkTagLink.tag_id == tag_id)
    )
    await session.delete(tag)
    await session.commit()


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #

async def list_groups(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookBookmarkGroup).order_by(SpyLookBookmarkGroup.sort_order)
    result = await session.execute(stmt)
    groups = list(result.scalars().all())
    # Batch-count bookmarks per group
    items: list[dict[str, Any]] = []
    for g in groups:
        count_stmt = select(func.count(SpyLookBookmark.id)).where(
            SpyLookBookmark.group_id == g.id
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar_one()
        items.append(_group_item(g, count))
    return items


async def get_group_row(
    session: AsyncSession, group_id: int
) -> SpyLookBookmarkGroup | None:
    return await session.get(SpyLookBookmarkGroup, group_id)


async def create_group(
    session: AsyncSession, name: str, sort_order: int = 0
) -> dict[str, Any]:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("分组名不能为空")
    existing = await session.execute(
        select(SpyLookBookmarkGroup).where(SpyLookBookmarkGroup.name == cleaned)
    )
    if existing.scalars().first() is not None:
        raise ValueError("分组名已存在")
    group = SpyLookBookmarkGroup(name=cleaned, sort_order=sort_order)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _group_item(group, 0)


async def update_group(
    session: AsyncSession,
    group_id: int,
    *,
    name: str | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    group = await get_group_row(session, group_id)
    if group is None:
        raise LookupError("分组不存在")
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("分组名不能为空")
        other = await session.execute(
            select(SpyLookBookmarkGroup).where(
                SpyLookBookmarkGroup.name == cleaned,
                SpyLookBookmarkGroup.id != group_id,
            )
        )
        if other.scalars().first() is not None:
            raise ValueError("分组名已存在")
        group.name = cleaned
    if sort_order is not None:
        group.sort_order = sort_order
    group.updated_at = datetime.utcnow()
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _group_item(group)


async def delete_group(session: AsyncSession, group_id: int) -> None:
    # Check if group has bookmarks
    count_stmt = select(func.count(SpyLookBookmark.id)).where(
        SpyLookBookmark.group_id == group_id
    )
    count_result = await session.execute(count_stmt)
    count = count_result.scalar_one()
    if count > 0:
        raise ValueError(
            f"该分组下还有 {count} 个书签，无法删除。请先将书签移至其他分组或删除。"
        )
    group = await get_group_row(session, group_id)
    if group is None:
        raise LookupError("分组不存在")
    await session.delete(group)
    await session.commit()


# --------------------------------------------------------------------------- #
# Bookmarks
# --------------------------------------------------------------------------- #

async def _bookmark_item(
    session: AsyncSession, row: SpyLookBookmark
) -> dict[str, Any]:
    return {
        "id": row.id,
        "url": row.url,
        "title": row.title,
        "favicon_url": row.favicon_url,
        "group_id": row.group_id,
        "pinned": row.pinned,
        "access_count": row.access_count,
        "last_accessed_at": _iso(row.last_accessed_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "tags": await _tags_for_bookmark(session, row.id),  # type: ignore[arg-type]
    }


async def list_bookmarks(
    session: AsyncSession,
    *,
    q: str | None = None,
    group_id: int | None = None,
    tag_ids: list[int] | None = None,
    pinned_only: bool = False,
) -> list[dict[str, Any]]:
    stmt = select(SpyLookBookmark)

    if pinned_only:
        stmt = stmt.where(SpyLookBookmark.pinned == True)  # noqa: E712
    else:
        if q and q.strip():
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    SpyLookBookmark.title.ilike(like),  # type: ignore[attr-defined]
                    SpyLookBookmark.url.ilike(like),  # type: ignore[attr-defined]
                )
            )
        if group_id is not None:
            stmt = stmt.where(SpyLookBookmark.group_id == group_id)
        if tag_ids:
            stmt = (
                stmt.join(
                    SpyLookBookmarkTagLink,
                    SpyLookBookmarkTagLink.bookmark_id == SpyLookBookmark.id,
                )
                .where(SpyLookBookmarkTagLink.tag_id.in_(tag_ids))
                .distinct()
            )

    stmt = stmt.order_by(SpyLookBookmark.access_count.desc())
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [await _bookmark_item(session, row) for row in rows]


async def get_bookmark_detail(
    session: AsyncSession, bookmark_id: int
) -> dict[str, Any] | None:
    row = await session.get(SpyLookBookmark, bookmark_id)
    if row is None:
        return None
    return await _bookmark_item(session, row)


async def get_bookmark_by_url(
    session: AsyncSession, url: str
) -> SpyLookBookmark | None:
    normalized = normalize_url(url)
    stmt = select(SpyLookBookmark).where(SpyLookBookmark.url == normalized)
    result = await session.execute(stmt)
    return result.scalars().first()


async def create_bookmark(
    session: AsyncSession,
    url: str,
    title: str = "",
    favicon_url: str = "",
    group_id: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_url(url)
    if not normalized:
        raise ValueError("URL 不能为空")
    # Check for duplicate
    existing = await get_bookmark_by_url(session, normalized)
    if existing is not None:
        raise ValueError("该 URL 已存在")
    now = datetime.utcnow()
    bookmark = SpyLookBookmark(
        url=normalized,
        title=title.strip(),
        favicon_url=favicon_url,
        group_id=group_id,
        pinned=False,
        access_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(bookmark)
    await session.commit()
    await session.refresh(bookmark)
    return await _bookmark_item(session, bookmark)


async def update_bookmark(
    session: AsyncSession,
    bookmark_id: int,
    *,
    title: str | None = None,
    favicon_url: str | None = None,
    group_id: int | None = None,
    pinned: bool | None = None,
) -> dict[str, Any]:
    bookmark = await session.get(SpyLookBookmark, bookmark_id)
    if bookmark is None:
        raise LookupError("书签不存在")
    if title is not None:
        bookmark.title = title.strip()
    if favicon_url is not None:
        bookmark.favicon_url = favicon_url
    if group_id is not None:
        bookmark.group_id = group_id
    if pinned is not None:
        bookmark.pinned = pinned
    bookmark.updated_at = datetime.utcnow()
    session.add(bookmark)
    await session.commit()
    await session.refresh(bookmark)
    return await _bookmark_item(session, bookmark)


async def delete_bookmark(session: AsyncSession, bookmark_id: int) -> None:
    bookmark = await session.get(SpyLookBookmark, bookmark_id)
    if bookmark is None:
        raise LookupError("书签不存在")
    # Clean up tag links
    await session.execute(
        delete(SpyLookBookmarkTagLink).where(
            SpyLookBookmarkTagLink.bookmark_id == bookmark_id
        )
    )
    # Clean up access logs
    await session.execute(
        delete(SpyLookBookmarkAccessLog).where(
            SpyLookBookmarkAccessLog.bookmark_id == bookmark_id
        )
    )
    await session.delete(bookmark)
    await session.commit()


async def set_bookmark_tags(
    session: AsyncSession, bookmark_id: int, tag_ids: list[int]
) -> dict[str, Any]:
    bookmark = await session.get(SpyLookBookmark, bookmark_id)
    if bookmark is None:
        raise LookupError("书签不存在")
    unique_ids = list(dict.fromkeys(tag_ids))
    if unique_ids:
        result = await session.execute(
            select(SpyLookBookmarkTag).where(SpyLookBookmarkTag.id.in_(unique_ids))
        )
        found = {t.id for t in result.scalars().all()}
        missing = [i for i in unique_ids if i not in found]
        if missing:
            raise ValueError(f"标签不存在: {missing}")
    await session.execute(
        delete(SpyLookBookmarkTagLink).where(
            SpyLookBookmarkTagLink.bookmark_id == bookmark_id
        )
    )
    for tid in unique_ids:
        session.add(SpyLookBookmarkTagLink(bookmark_id=bookmark_id, tag_id=tid))
    bookmark.updated_at = datetime.utcnow()
    session.add(bookmark)
    await session.commit()
    detail = await get_bookmark_detail(session, bookmark_id)
    assert detail is not None
    return detail


async def record_access(session: AsyncSession, bookmark_id: int) -> dict[str, Any]:
    bookmark = await session.get(SpyLookBookmark, bookmark_id)
    if bookmark is None:
        raise LookupError("书签不存在")
    now = datetime.utcnow()
    # Insert access log entry
    session.add(
        SpyLookBookmarkAccessLog(bookmark_id=bookmark_id, accessed_at=now)
    )
    # Update denormalized counters
    bookmark.access_count += 1
    bookmark.last_accessed_at = now
    bookmark.updated_at = now
    session.add(bookmark)
    await session.commit()
    await session.refresh(bookmark)
    return await _bookmark_item(session, bookmark)


async def get_top5(session: AsyncSession) -> list[dict[str, Any]]:
    """Get top 5 bookmarks by access frequency in the last 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    stmt = (
        select(
            SpyLookBookmark,
            func.count(SpyLookBookmarkAccessLog.id).label("access_count_7d"),
        )
        .join(
            SpyLookBookmarkAccessLog,
            SpyLookBookmarkAccessLog.bookmark_id == SpyLookBookmark.id,
        )
        .where(SpyLookBookmarkAccessLog.accessed_at >= cutoff)
        .group_by(SpyLookBookmark.id)
        .order_by(func.count(SpyLookBookmarkAccessLog.id).desc())
        .limit(5)
    )
    result = await session.execute(stmt)
    items: list[dict[str, Any]] = []
    for row in result.all():
        bookmark = row[0]
        item = await _bookmark_item(session, bookmark)
        item["access_count_7d"] = row[1]
        items.append(item)
    return items


async def prune_old_access_logs(session: AsyncSession, days: int = 30) -> int:
    """Delete access logs older than the given number of days. Returns deleted count."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        delete(SpyLookBookmarkAccessLog).where(
            SpyLookBookmarkAccessLog.accessed_at < cutoff
        )
    )
    await session.commit()
    return result.rowcount
