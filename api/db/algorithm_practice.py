from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import (
    SpyLookAlgorithmProblem,
    SpyLookAlgorithmTag,
    SpyLookAlgorithmTagLink,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def _tag_item(tag: SpyLookAlgorithmTag) -> dict[str, Any]:
    return {"id": tag.id, "name": tag.name, "color": tag.color}


async def _tags_for_problem(
    session: AsyncSession, problem_id: int
) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookAlgorithmTag)
        .join(
            SpyLookAlgorithmTagLink,
            SpyLookAlgorithmTagLink.tag_id == SpyLookAlgorithmTag.id,
        )
        .where(SpyLookAlgorithmTagLink.problem_id == problem_id)
        .order_by(SpyLookAlgorithmTag.name)
    )
    result = await session.execute(stmt)
    return [_tag_item(t) for t in result.scalars().all()]


def _problem_list_item(
    row: SpyLookAlgorithmProblem, tags: list[dict[str, Any]]
) -> dict[str, Any]:
    """Lightweight item for list view — no full description/code/thought."""
    preview = (row.description or "")[:200]
    return {
        "id": row.id,
        "title": row.title,
        "description_preview": preview,
        "tags": tags,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


async def _problem_item(
    session: AsyncSession, row: SpyLookAlgorithmProblem
) -> dict[str, Any]:
    """Full detail item — includes description, solution_code, thought."""
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "description_preview": (row.description or "")[:200],
        "solution_code": row.solution_code,
        "thought": row.thought,
        "tags": await _tags_for_problem(session, row.id),  # type: ignore[arg-type]
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


# --------------------------------------------------------------------------- #
# Tags
# --------------------------------------------------------------------------- #


async def list_tags(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookAlgorithmTag).order_by(SpyLookAlgorithmTag.name)
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
        select(SpyLookAlgorithmTag).where(SpyLookAlgorithmTag.name == cleaned)
    )
    if existing.scalars().first() is not None:
        raise ValueError("标签已存在")
    tag = SpyLookAlgorithmTag(name=cleaned, color=color)
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
    tag = await session.get(SpyLookAlgorithmTag, tag_id)
    if tag is None:
        raise LookupError("标签不存在")
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("标签名不能为空")
        other = await session.execute(
            select(SpyLookAlgorithmTag).where(
                SpyLookAlgorithmTag.name == cleaned,
                SpyLookAlgorithmTag.id != tag_id,
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
    tag = await session.get(SpyLookAlgorithmTag, tag_id)
    if tag is None:
        raise LookupError("标签不存在")
    await session.execute(
        delete(SpyLookAlgorithmTagLink).where(
            SpyLookAlgorithmTagLink.tag_id == tag_id
        )
    )
    await session.delete(tag)
    await session.commit()


# --------------------------------------------------------------------------- #
# Problems
# --------------------------------------------------------------------------- #


async def list_problems(
    session: AsyncSession,
    *,
    q: str | None = None,
    tag_ids: list[int] | None = None,
    sort: str = "updated_desc",
) -> list[dict[str, Any]]:
    stmt = select(SpyLookAlgorithmProblem)

    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                SpyLookAlgorithmProblem.title.ilike(like),  # type: ignore[attr-defined]
            )
        )

    if tag_ids:
        stmt = (
            stmt.join(
                SpyLookAlgorithmTagLink,
                SpyLookAlgorithmTagLink.problem_id == SpyLookAlgorithmProblem.id,
            )
            .where(SpyLookAlgorithmTagLink.tag_id.in_(tag_ids))
            .distinct()
        )

    if sort == "updated_asc":
        stmt = stmt.order_by(SpyLookAlgorithmProblem.updated_at.asc())
    elif sort == "created_desc":
        stmt = stmt.order_by(SpyLookAlgorithmProblem.created_at.desc())
    else:
        stmt = stmt.order_by(SpyLookAlgorithmProblem.updated_at.desc())

    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    items: list[dict[str, Any]] = []
    for row in rows:
        tags = await _tags_for_problem(session, row.id)  # type: ignore[arg-type]
        items.append(_problem_list_item(row, tags))
    return items


async def get_problem_detail(
    session: AsyncSession, problem_id: int
) -> dict[str, Any] | None:
    row = await session.get(SpyLookAlgorithmProblem, problem_id)
    if row is None:
        return None
    return await _problem_item(session, row)


async def create_problem(
    session: AsyncSession,
    title: str,
    description: str = "",
    tag_ids: list[int] | None = None,
) -> dict[str, Any]:
    cleaned_title = (title or "").strip()
    if not cleaned_title:
        raise ValueError("标题不能为空")
    now = datetime.utcnow()
    problem = SpyLookAlgorithmProblem(
        title=cleaned_title,
        description=description,
        solution_code="",
        thought="",
        created_at=now,
        updated_at=now,
    )
    session.add(problem)
    await session.commit()
    await session.refresh(problem)

    # Set tags if provided
    if tag_ids:
        unique_ids = list(dict.fromkeys(tag_ids))
        result = await session.execute(
            select(SpyLookAlgorithmTag).where(
                SpyLookAlgorithmTag.id.in_(unique_ids)
            )
        )
        found = {t.id for t in result.scalars().all()}
        missing = [i for i in unique_ids if i not in found]
        if missing:
            raise ValueError(f"标签不存在: {missing}")
        for tid in unique_ids:
            session.add(
                SpyLookAlgorithmTagLink(problem_id=problem.id, tag_id=tid)
            )
        await session.commit()
        await session.refresh(problem)

    return await _problem_item(session, problem)


async def update_problem(
    session: AsyncSession,
    problem_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    solution_code: str | None = None,
    thought: str | None = None,
) -> dict[str, Any]:
    problem = await session.get(SpyLookAlgorithmProblem, problem_id)
    if problem is None:
        raise LookupError("题目不存在")
    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        problem.title = cleaned
    if description is not None:
        problem.description = description
    if solution_code is not None:
        problem.solution_code = solution_code
    if thought is not None:
        problem.thought = thought
    problem.updated_at = datetime.utcnow()
    session.add(problem)
    await session.commit()
    await session.refresh(problem)
    return await _problem_item(session, problem)


async def delete_problem(session: AsyncSession, problem_id: int) -> None:
    problem = await session.get(SpyLookAlgorithmProblem, problem_id)
    if problem is None:
        raise LookupError("题目不存在")
    await session.execute(
        delete(SpyLookAlgorithmTagLink).where(
            SpyLookAlgorithmTagLink.problem_id == problem_id
        )
    )
    await session.delete(problem)
    await session.commit()


async def set_problem_tags(
    session: AsyncSession, problem_id: int, tag_ids: list[int]
) -> dict[str, Any]:
    problem = await session.get(SpyLookAlgorithmProblem, problem_id)
    if problem is None:
        raise LookupError("题目不存在")
    unique_ids = list(dict.fromkeys(tag_ids))
    if unique_ids:
        result = await session.execute(
            select(SpyLookAlgorithmTag).where(
                SpyLookAlgorithmTag.id.in_(unique_ids)
            )
        )
        found = {t.id for t in result.scalars().all()}
        missing = [i for i in unique_ids if i not in found]
        if missing:
            raise ValueError(f"标签不存在: {missing}")
    await session.execute(
        delete(SpyLookAlgorithmTagLink).where(
            SpyLookAlgorithmTagLink.problem_id == problem_id
        )
    )
    for tid in unique_ids:
        session.add(SpyLookAlgorithmTagLink(problem_id=problem_id, tag_id=tid))
    problem.updated_at = datetime.utcnow()
    session.add(problem)
    await session.commit()
    detail = await get_problem_detail(session, problem_id)
    assert detail is not None
    return detail
