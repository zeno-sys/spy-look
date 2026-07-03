from __future__ import annotations

import re
import secrets
import time
from typing import Any

from sqlalchemy import delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from config import LEGACY_UNKNOWN_APP_ID
from db.models import SpyLookClientKey, SpyLookPendingGatewayKey
from db.upstreams import mask_api_key

APP_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_PENDING_GATEWAY_KEY_TTL_SEC = 600


def validate_app_id(raw: str) -> str:
    text = str(raw or "").strip()
    if not text or not APP_ID_RE.fullmatch(text):
        raise ValueError(
            "app_id 须为 1–64 位，以字母或数字开头，仅可含字母、数字、点、下划线、连字符"
        )
    return text


async def _scalar_one(session: AsyncSession, stmt) -> Any:
    result = await session.execute(stmt)
    return result.scalars().first()


async def _scalar_all(session: AsyncSession, stmt) -> list[Any]:
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_client_api_key(session: AsyncSession) -> str:
    stmt = select(SpyLookClientKey).order_by(SpyLookClientKey.id.asc()).limit(1)
    row = await _scalar_one(session, stmt)
    return str(row.api_key) if row and str(row.api_key or "").strip() else ""


async def get_client_api_key_by_app_id(session: AsyncSession, app_id: str) -> str | None:
    aid = str(app_id or "").strip()
    if not aid:
        return None
    stmt = select(SpyLookClientKey).where(SpyLookClientKey.app_id == aid).limit(1)
    row = await _scalar_one(session, stmt)
    if not row or not str(row.api_key or "").strip():
        return None
    return str(row.api_key)


async def get_client_api_key_meta(session: AsyncSession) -> dict[str, Any]:
    items = await list_client_keys_meta(session)
    first_mask = items[0]["api_key_masked"] if items else ""
    return {"items": items, "gateway_api_key_masked": first_mask}


async def list_client_keys_meta(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookClientKey).order_by(SpyLookClientKey.id.asc())
    rows = await _scalar_all(session, stmt)
    out: list[dict[str, Any]] = []
    for r in rows:
        d = r.model_dump(mode='json')
        d["api_key_masked"] = mask_api_key(d.pop("api_key"))
        out.append(d)
    return out


async def get_client_key_plain(session: AsyncSession, key_id: int) -> str | None:
    row = await session.get(SpyLookClientKey, key_id)
    if not row:
        return None
    return str(row.api_key or "")


async def resolve_app_id_by_api_key(session: AsyncSession, provided_key: str) -> str | None:
    text = str(provided_key or "").strip()
    if not text:
        return None
    stmt = select(SpyLookClientKey).where(SpyLookClientKey.api_key == text).limit(1)
    row = await _scalar_one(session, stmt)
    if not row:
        return None
    app_id = str(row.app_id or "").strip()
    return app_id or LEGACY_UNKNOWN_APP_ID


async def client_api_key_is_valid(session: AsyncSession, provided_key: str) -> bool:
    return await resolve_app_id_by_api_key(session, provided_key) is not None


def generate_gateway_api_key() -> str:
    return f"sk-spy-{secrets.token_urlsafe(32)}"


async def register_pending_gateway_key(session: AsyncSession, key: str) -> None:
    text = str(key or "").strip()
    if not text:
        return
    now = time.time()
    await session.execute(
        delete(SpyLookPendingGatewayKey).where(SpyLookPendingGatewayKey.expires_at < now)
    )
    pending = SpyLookPendingGatewayKey(api_key=text, expires_at=now + _PENDING_GATEWAY_KEY_TTL_SEC)
    await session.merge(pending)
    await session.commit()


async def consume_pending_gateway_key(session: AsyncSession, key: str) -> bool:
    text = str(key or "").strip()
    if not text:
        return False
    now = time.time()
    await session.execute(
        delete(SpyLookPendingGatewayKey).where(SpyLookPendingGatewayKey.expires_at < now)
    )
    stmt = delete(SpyLookPendingGatewayKey).where(
        SpyLookPendingGatewayKey.api_key == text,
        SpyLookPendingGatewayKey.expires_at >= now,
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0 if result.rowcount else False


async def add_client_key(session: AsyncSession, api_key: str, app_id: str) -> int:
    text = str(api_key or "").strip()
    if not text:
        raise ValueError("api_key must be non-empty")
    aid = validate_app_id(app_id)

    existing_key = await _scalar_one(
        session,
        select(SpyLookClientKey).where(SpyLookClientKey.api_key == text),
    )
    if existing_key:
        raise ValueError("该 API Key 已存在")

    existing_app = await _scalar_one(
        session,
        select(SpyLookClientKey).where(SpyLookClientKey.app_id == aid),
    )
    if existing_app:
        raise ValueError("该 app_id 已存在")

    client_key = SpyLookClientKey(api_key=text, app_id=aid)
    session.add(client_key)
    await session.commit()
    await session.refresh(client_key)
    return client_key.id


async def update_client_key_app_id(session: AsyncSession, key_id: int, app_id: str) -> None:
    aid = validate_app_id(app_id)
    row = await session.get(SpyLookClientKey, key_id)
    if not row:
        raise LookupError("client key not found")

    existing = await _scalar_one(
        session,
        select(SpyLookClientKey).where(SpyLookClientKey.app_id == aid),
    )
    if existing and existing.id != key_id:
        raise ValueError("该 app_id 已存在")

    row.app_id = aid
    await session.commit()


async def delete_client_key(session: AsyncSession, key_id: int) -> None:
    rows = await _scalar_all(session, select(SpyLookClientKey))
    if len(rows) <= 1:
        raise ValueError("至少保留一条对外 API Key")

    row = await session.get(SpyLookClientKey, key_id)
    if not row:
        raise LookupError("client key not found")
    await session.delete(row)
    await session.commit()
