from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import (
    SpyLookAgentSkill,
    SpyLookAgentSkillTag,
    SpyLookAgentSkillTagLink,
    SpyLookAgentSkillVersion,
)
from tools.agent_resources.services.skill_package import (
    ParsedSkillPackage,
    extract_skill_md,
    list_package_files,
)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def _tag_item(tag: SpyLookAgentSkillTag) -> dict[str, Any]:
    return {"id": tag.id, "name": tag.name, "color": tag.color}


async def _tags_for_skill(session: AsyncSession, skill_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookAgentSkillTag)
        .join(
            SpyLookAgentSkillTagLink,
            SpyLookAgentSkillTagLink.tag_id == SpyLookAgentSkillTag.id,
        )
        .where(SpyLookAgentSkillTagLink.skill_id == skill_id)
        .order_by(SpyLookAgentSkillTag.name)
    )
    result = await session.execute(stmt)
    return [_tag_item(t) for t in result.scalars().all()]


async def _skill_list_item(session: AsyncSession, row: SpyLookAgentSkill) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "current_version": row.current_version,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "tags": await _tags_for_skill(session, row.id),  # type: ignore[arg-type]
    }


async def get_skill_row(session: AsyncSession, skill_id: int) -> SpyLookAgentSkill | None:
    return await session.get(SpyLookAgentSkill, skill_id)


async def get_skill_by_name(session: AsyncSession, name: str) -> SpyLookAgentSkill | None:
    stmt = select(SpyLookAgentSkill).where(SpyLookAgentSkill.name == name)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_version_row(
    session: AsyncSession, skill_id: int, version: int
) -> SpyLookAgentSkillVersion | None:
    stmt = select(SpyLookAgentSkillVersion).where(
        SpyLookAgentSkillVersion.skill_id == skill_id,
        SpyLookAgentSkillVersion.version == version,
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_current_package(session: AsyncSession, skill: SpyLookAgentSkill) -> bytes:
    ver = await get_version_row(session, skill.id, skill.current_version)  # type: ignore[arg-type]
    if ver is None:
        raise ValueError("当前版本数据缺失")
    return ver.package_zip


async def list_skills(
    session: AsyncSession,
    *,
    q: str | None = None,
    tag_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    stmt = select(SpyLookAgentSkill)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                SpyLookAgentSkill.name.ilike(like),  # type: ignore[attr-defined]
                SpyLookAgentSkill.description.ilike(like),  # type: ignore[attr-defined]
            )
        )
    if tag_ids:
        stmt = (
            stmt.join(
                SpyLookAgentSkillTagLink,
                SpyLookAgentSkillTagLink.skill_id == SpyLookAgentSkill.id,
            )
            .where(SpyLookAgentSkillTagLink.tag_id.in_(tag_ids))
            .distinct()
        )
    stmt = stmt.order_by(SpyLookAgentSkill.updated_at.desc())
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [await _skill_list_item(session, row) for row in rows]


async def list_versions(session: AsyncSession, skill_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookAgentSkillVersion)
        .where(SpyLookAgentSkillVersion.skill_id == skill_id)
        .order_by(SpyLookAgentSkillVersion.version.desc())
    )
    result = await session.execute(stmt)
    items = []
    for row in result.scalars().all():
        items.append(
            {
                "id": row.id,
                "version": row.version,
                "changelog": row.changelog,
                "size_bytes": row.size_bytes,
                "created_at": _iso(row.created_at),
            }
        )
    return items


async def get_skill_detail(session: AsyncSession, skill_id: int) -> dict[str, Any] | None:
    row = await get_skill_row(session, skill_id)
    if row is None:
        return None
    package = await get_current_package(session, row)
    item = await _skill_list_item(session, row)
    item["skill_md"] = extract_skill_md(package)
    item["files"] = list_package_files(package)
    item["size_bytes"] = len(package)
    item["versions"] = await list_versions(session, skill_id)
    return item


async def _append_version(
    session: AsyncSession,
    skill: SpyLookAgentSkill,
    package: ParsedSkillPackage,
    changelog: str,
) -> SpyLookAgentSkill:
    note = (changelog or "").strip()
    if not note:
        raise ValueError("变更说明不能为空")
    now = datetime.utcnow()
    next_ver = (skill.current_version or 0) + 1
    # first create uses current_version=0 sentinel before insert — caller sets up
    if skill.id is None:
        next_ver = 1
    elif skill.current_version == 0:
        next_ver = 1

    skill.name = package.name
    skill.description = package.description
    skill.current_version = next_ver
    skill.updated_at = now
    session.add(skill)
    await session.flush()

    session.add(
        SpyLookAgentSkillVersion(
            skill_id=skill.id,
            version=next_ver,
            changelog=note,
            package_zip=package.package_zip,
            size_bytes=package.size_bytes,
            created_at=now,
        )
    )
    await session.commit()
    await session.refresh(skill)
    return skill


async def create_or_version_skill(
    session: AsyncSession,
    package: ParsedSkillPackage,
    changelog: str,
) -> dict[str, Any]:
    existing = await get_skill_by_name(session, package.name)
    if existing is None:
        now = datetime.utcnow()
        skill = SpyLookAgentSkill(
            name=package.name,
            description=package.description,
            current_version=0,
            created_at=now,
            updated_at=now,
        )
        session.add(skill)
        await session.flush()
        skill = await _append_version(session, skill, package, changelog)
    else:
        skill = await _append_version(session, existing, package, changelog)
    detail = await get_skill_detail(session, skill.id)  # type: ignore[arg-type]
    assert detail is not None
    return detail


async def update_skill_package(
    session: AsyncSession,
    skill_id: int,
    package: ParsedSkillPackage,
    changelog: str,
) -> dict[str, Any]:
    skill = await get_skill_row(session, skill_id)
    if skill is None:
        raise LookupError("Skill 不存在")

    # name change: ensure no conflict with another skill
    if package.name != skill.name:
        other = await get_skill_by_name(session, package.name)
        if other is not None and other.id != skill.id:
            raise ValueError(f"Skill name「{package.name}」已被占用")

    skill = await _append_version(session, skill, package, changelog)
    detail = await get_skill_detail(session, skill.id)  # type: ignore[arg-type]
    assert detail is not None
    return detail


async def restore_version(
    session: AsyncSession,
    skill_id: int,
    version: int,
    changelog: str,
) -> dict[str, Any]:
    skill = await get_skill_row(session, skill_id)
    if skill is None:
        raise LookupError("Skill 不存在")
    ver = await get_version_row(session, skill_id, version)
    if ver is None:
        raise LookupError("版本不存在")
    from tools.agent_resources.services.skill_package import parse_zip_bytes

    package = parse_zip_bytes(ver.package_zip)
    note = (changelog or "").strip() or f"恢复自 v{version}"
    return await update_skill_package(session, skill_id, package, note)


async def delete_skill(session: AsyncSession, skill_id: int) -> None:
    skill = await get_skill_row(session, skill_id)
    if skill is None:
        raise LookupError("Skill 不存在")
    await session.execute(
        delete(SpyLookAgentSkillTagLink).where(SpyLookAgentSkillTagLink.skill_id == skill_id)
    )
    await session.execute(
        delete(SpyLookAgentSkillVersion).where(SpyLookAgentSkillVersion.skill_id == skill_id)
    )
    await session.delete(skill)
    await session.commit()


async def download_package(
    session: AsyncSession, skill_id: int, version: int | None = None
) -> tuple[str, bytes]:
    skill = await get_skill_row(session, skill_id)
    if skill is None:
        raise LookupError("Skill 不存在")
    ver_num = version if version is not None else skill.current_version
    ver = await get_version_row(session, skill_id, ver_num)
    if ver is None:
        raise LookupError("版本不存在")
    # package name may differ if restored; parse current stored name from zip path
    from tools.agent_resources.services.skill_package import parse_zip_bytes

    parsed = parse_zip_bytes(ver.package_zip)
    return f"{parsed.name}.zip", ver.package_zip


# ----- tags -----


async def list_tags(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookAgentSkillTag).order_by(SpyLookAgentSkillTag.name)
    result = await session.execute(stmt)
    return [_tag_item(t) for t in result.scalars().all()]


async def create_tag(session: AsyncSession, name: str, color: str) -> dict[str, Any]:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("标签名不能为空")
    color = (color or "#64748b").strip() or "#64748b"
    existing = await session.execute(
        select(SpyLookAgentSkillTag).where(SpyLookAgentSkillTag.name == cleaned)
    )
    if existing.scalars().first() is not None:
        raise ValueError("标签已存在")
    tag = SpyLookAgentSkillTag(name=cleaned, color=color)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return _tag_item(tag)


async def update_tag(
    session: AsyncSession, tag_id: int, *, name: str | None = None, color: str | None = None
) -> dict[str, Any]:
    tag = await session.get(SpyLookAgentSkillTag, tag_id)
    if tag is None:
        raise LookupError("标签不存在")
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("标签名不能为空")
        other = await session.execute(
            select(SpyLookAgentSkillTag).where(
                SpyLookAgentSkillTag.name == cleaned,
                SpyLookAgentSkillTag.id != tag_id,
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
    tag = await session.get(SpyLookAgentSkillTag, tag_id)
    if tag is None:
        raise LookupError("标签不存在")
    await session.execute(
        delete(SpyLookAgentSkillTagLink).where(SpyLookAgentSkillTagLink.tag_id == tag_id)
    )
    await session.delete(tag)
    await session.commit()


async def set_skill_tags(
    session: AsyncSession, skill_id: int, tag_ids: list[int]
) -> dict[str, Any]:
    skill = await get_skill_row(session, skill_id)
    if skill is None:
        raise LookupError("Skill 不存在")
    unique_ids = list(dict.fromkeys(tag_ids))
    if unique_ids:
        result = await session.execute(
            select(SpyLookAgentSkillTag).where(SpyLookAgentSkillTag.id.in_(unique_ids))
        )
        found = {t.id for t in result.scalars().all()}
        missing = [i for i in unique_ids if i not in found]
        if missing:
            raise ValueError(f"标签不存在: {missing}")
    await session.execute(
        delete(SpyLookAgentSkillTagLink).where(SpyLookAgentSkillTagLink.skill_id == skill_id)
    )
    for tid in unique_ids:
        session.add(SpyLookAgentSkillTagLink(skill_id=skill_id, tag_id=tid))
    skill.updated_at = datetime.utcnow()
    session.add(skill)
    await session.commit()
    detail = await get_skill_detail(session, skill_id)
    assert detail is not None
    return detail
