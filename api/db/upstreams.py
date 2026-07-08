from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import SpyLookUpstream
from db.public_models import count_upstream_route_refs, list_upstream_bindings


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
    d = row.model_dump(mode="json")
    d.pop("api_key", None)
    d["api_key_masked"] = mask_api_key(row.api_key)
    return d


def _upstream_row_runtime(row: SpyLookUpstream) -> dict[str, Any]:
    return row.model_dump(mode="json")


async def _scalar_one(session: AsyncSession, stmt) -> Any:
    result = await session.execute(stmt)
    return result.scalars().first()


async def _scalar_all(session: AsyncSession, stmt) -> list[Any]:
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_upstreams(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookUpstream).order_by(SpyLookUpstream.id.asc())
    rows = await _scalar_all(session, stmt)
    return [_upstream_row_public(row) for row in rows]


async def list_enabled_upstream_rows(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookUpstream)
        .where(SpyLookUpstream.enabled == True)
        .order_by(SpyLookUpstream.id.asc())
    )
    rows = await _scalar_all(session, stmt)
    return [_upstream_row_runtime(row) for row in rows]


async def get_upstream(session: AsyncSession, upstream_id: int) -> dict[str, Any] | None:
    row = await session.get(SpyLookUpstream, upstream_id)
    return _upstream_row_public(row) if row else None


async def get_upstream_runtime(session: AsyncSession, upstream_id: int) -> dict[str, Any] | None:
    row = await session.get(SpyLookUpstream, upstream_id)
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
) -> int:
    upstream = SpyLookUpstream(
        name=name.strip(),
        base_url=base_url.strip(),
        api_key=api_key,
        trust_env=trust_env,
        timeout_seconds=float(timeout_seconds),
        enabled=enabled,
    )
    session.add(upstream)
    await session.commit()
    await session.refresh(upstream)
    return upstream.id or 0


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
    refs = await count_upstream_route_refs(session, upstream_id)
    if refs > 0:
        bindings = await list_upstream_bindings(session, upstream_id)
        names = "、".join(
            f"{item['public_model_name']}/{item['upstream_model']}"
            for item in bindings
        )
        raise ValueError(f"该模型源仍被以下对外模型绑定：{names}，请先在对外模型配置中解除绑定后再删除")
    await session.delete(upstream)
    await session.commit()
    return True
