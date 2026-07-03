from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import SpyLookUpstream


def mask_api_key(api_key: str) -> str:
    text = str(api_key or "").strip()
    if not text:
        return ""
    n = len(text)
    if n <= 8:
        return "*" * min(n, 4)
    keep = 4
    return f"{text[:keep]}****{text[-keep:]}"


def _upstream_row_public(row: SpyLookUpstream) -> dict[str, Any]:
    d = row.model_dump(mode='json')
    d["api_key_masked"] = mask_api_key(d.pop("api_key"))
    return d


def _upstream_row_runtime(row: SpyLookUpstream) -> dict[str, Any]:
    return row.model_dump(mode='json')


async def _scalar_one(session: AsyncSession, stmt) -> Any:
    result = await session.execute(stmt)
    return result.scalars().first()


async def _scalar_all(session: AsyncSession, stmt) -> list[Any]:
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_upstreams(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookUpstream).order_by(SpyLookUpstream.is_default.desc(), SpyLookUpstream.id.asc())
    rows = await _scalar_all(session, stmt)
    return [_upstream_row_public(row) for row in rows]


async def list_failover_upstream_rows(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookUpstream)
        .where(SpyLookUpstream.enabled == True)
        .order_by(SpyLookUpstream.is_default.desc(), SpyLookUpstream.id.asc())
    )
    rows = await _scalar_all(session, stmt)
    return [_upstream_row_runtime(row) for row in rows]


async def get_upstream(session: AsyncSession, upstream_id: int) -> dict[str, Any] | None:
    row = await session.get(SpyLookUpstream, upstream_id)
    return _upstream_row_public(row) if row else None


async def get_upstream_runtime(session: AsyncSession, upstream_id: int) -> dict[str, Any] | None:
    row = await session.get(SpyLookUpstream, upstream_id)
    return _upstream_row_runtime(row) if row else None


async def get_default_upstream_row(session: AsyncSession) -> dict[str, Any] | None:
    stmt = (
        select(SpyLookUpstream)
        .where(SpyLookUpstream.enabled == True, SpyLookUpstream.is_default == True)
        .order_by(SpyLookUpstream.id.asc())
        .limit(1)
    )
    row = await _scalar_one(session, stmt)
    if row:
        return _upstream_row_runtime(row)

    stmt = (
        select(SpyLookUpstream)
        .where(SpyLookUpstream.enabled == True)
        .order_by(SpyLookUpstream.id.asc())
        .limit(1)
    )
    row = await _scalar_one(session, stmt)
    return _upstream_row_runtime(row) if row else None


async def create_upstream(
    session: AsyncSession,
    *,
    name: str,
    base_url: str,
    api_key: str,
    trust_env: bool = False,
    timeout_seconds: float = 60.0,
    enabled: bool = True,
    is_default: bool = False,
) -> int:
    upstream = SpyLookUpstream(
        name=name.strip(),
        base_url=base_url.strip(),
        api_key=api_key,
        trust_env=trust_env,
        timeout_seconds=float(timeout_seconds),
        enabled=enabled,
        is_default=False,
    )
    session.add(upstream)
    await session.flush()
    new_id = upstream.id

    has_default = await _scalar_one(
        session,
        select(SpyLookUpstream).where(SpyLookUpstream.is_default == True),
    ) is not None

    if is_default or not has_default:
        await session.execute(
            update(SpyLookUpstream).values(is_default=False, updated_at=datetime.utcnow())
        )
        await session.execute(
            update(SpyLookUpstream).where(SpyLookUpstream.id == new_id).values(
                is_default=True, updated_at=datetime.utcnow()
            )
        )

    await session.commit()
    return new_id


async def update_upstream(
    session: AsyncSession,
    upstream_id: int,
    *,
    name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    trust_env: bool | None = None,
    timeout_seconds: float | None = None,
    enabled: bool | None = None,
) -> bool:
    upstream = await session.get(SpyLookUpstream, upstream_id)
    if not upstream:
        return False

    if name is not None:
        upstream.name = name.strip()
    if base_url is not None:
        upstream.base_url = base_url.strip()
    if api_key is not None and str(api_key).strip():
        upstream.api_key = str(api_key).strip()
    if trust_env is not None:
        upstream.trust_env = trust_env
    if timeout_seconds is not None:
        upstream.timeout_seconds = float(timeout_seconds)
    if enabled is not None:
        upstream.enabled = enabled
    upstream.updated_at = datetime.utcnow()
    await session.commit()
    return True


async def delete_upstream(session: AsyncSession, upstream_id: int) -> bool:
    upstream = await session.get(SpyLookUpstream, upstream_id)
    if not upstream:
        return False
    was_default = upstream.is_default
    await session.delete(upstream)

    if was_default:
        nxt = await _scalar_one(
            session,
            select(SpyLookUpstream).order_by(SpyLookUpstream.id.asc()).limit(1),
        )
        if nxt:
            await session.execute(
                update(SpyLookUpstream).values(is_default=False, updated_at=datetime.utcnow())
            )
            await session.execute(
                update(SpyLookUpstream).where(SpyLookUpstream.id == nxt.id).values(
                    is_default=True, updated_at=datetime.utcnow()
                )
            )

    await session.commit()
    return True


async def set_default_upstream(session: AsyncSession, upstream_id: int) -> bool:
    upstream = await session.get(SpyLookUpstream, upstream_id)
    if not upstream or not upstream.enabled:
        return False

    await session.execute(
        update(SpyLookUpstream).values(is_default=False, updated_at=datetime.utcnow())
    )
    await session.execute(
        update(SpyLookUpstream).where(SpyLookUpstream.id == upstream_id).values(
            is_default=True, updated_at=datetime.utcnow()
        )
    )
    await session.commit()
    return True
