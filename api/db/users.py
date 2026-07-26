from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import delete, func, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import SpyLookSession, SpyLookUser

USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
SESSION_HOURS_DEFAULT = 12
SESSION_DAYS_REMEMBER = 30
SESSION_DAYS_ABSOLUTE_MAX = 30


def validate_username(raw: str) -> str:
    text = str(raw or "").strip()
    if not text or not USERNAME_RE.fullmatch(text):
        raise ValueError(
            "用户名须为 1–64 位，以字母或数字开头，仅可含字母、数字、点、下划线、连字符"
        )
    return text


def validate_password(raw: str) -> str:
    text = str(raw or "")
    if len(text) < 8:
        raise ValueError("密码至少 8 位")
    return text


async def _scalar_one(session: AsyncSession, stmt) -> Any:
    result = await session.execute(stmt)
    return result.scalars().first()


async def _scalar_all(session: AsyncSession, stmt) -> list[Any]:
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(SpyLookUser))
    return int(result.scalar_one())


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[SpyLookUser]:
    return await _scalar_one(session, select(SpyLookUser).where(SpyLookUser.id == user_id))


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[SpyLookUser]:
    return await _scalar_one(
        session, select(SpyLookUser).where(SpyLookUser.username == username)
    )


async def get_owner(session: AsyncSession) -> Optional[SpyLookUser]:
    return await _scalar_one(
        session, select(SpyLookUser).where(SpyLookUser.role == ROLE_OWNER)
    )


async def list_users(session: AsyncSession) -> list[SpyLookUser]:
    return await _scalar_all(
        session, select(SpyLookUser).order_by(SpyLookUser.id.asc())
    )


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password_hash: str,
    role: str,
) -> SpyLookUser:
    now = datetime.utcnow()
    user = SpyLookUser(
        username=username,
        password_hash=password_hash,
        role=role,
        disabled=False,
        failed_login_count=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_password(
    session: AsyncSession, user: SpyLookUser, password_hash: str
) -> SpyLookUser:
    user.password_hash = password_hash
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_disabled(
    session: AsyncSession, user: SpyLookUser, disabled: bool
) -> SpyLookUser:
    user.disabled = disabled
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user: SpyLookUser) -> None:
    await session.execute(
        delete(SpyLookSession).where(SpyLookSession.user_id == user.id)
    )
    await session.delete(user)
    await session.commit()


async def record_login_failure(session: AsyncSession, user: SpyLookUser) -> SpyLookUser:
    user.failed_login_count = int(user.failed_login_count or 0) + 1
    if user.failed_login_count >= MAX_FAILED_LOGINS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)
        user.failed_login_count = 0
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def clear_login_failures(session: AsyncSession, user: SpyLookUser) -> SpyLookUser:
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def is_user_locked(user: SpyLookUser) -> bool:
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True
    return False


def session_expiry(remember: bool) -> datetime:
    if remember:
        delta = timedelta(days=SESSION_DAYS_REMEMBER)
    else:
        delta = timedelta(hours=SESSION_HOURS_DEFAULT)
    max_delta = timedelta(days=SESSION_DAYS_ABSOLUTE_MAX)
    if delta > max_delta:
        delta = max_delta
    return datetime.utcnow() + delta


async def create_session(
    session: AsyncSession, *, user_id: int, remember: bool
) -> SpyLookSession:
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    row = SpyLookSession(
        id=token,
        user_id=user_id,
        expires_at=session_expiry(remember),
        remember=remember,
        created_at=now,
        last_seen_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_session_by_id(
    session: AsyncSession, token: str
) -> Optional[SpyLookSession]:
    return await _scalar_one(
        session, select(SpyLookSession).where(SpyLookSession.id == token)
    )


async def touch_session(session: AsyncSession, token: str) -> None:
    await session.execute(
        update(SpyLookSession)
        .where(SpyLookSession.id == token)
        .values(last_seen_at=datetime.utcnow())
    )
    await session.commit()


async def delete_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(SpyLookSession).where(SpyLookSession.id == token))
    await session.commit()


async def revoke_user_sessions(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        delete(SpyLookSession).where(SpyLookSession.user_id == user_id)
    )
    await session.commit()
    return int(result.rowcount or 0)


async def purge_expired_sessions(session: AsyncSession) -> None:
    await session.execute(
        delete(SpyLookSession).where(SpyLookSession.expires_at < datetime.utcnow())
    )
    await session.commit()


def user_public(user: SpyLookUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "disabled": bool(user.disabled),
        "locked": is_user_locked(user),
        "created_at": user.created_at.isoformat() + "Z" if user.created_at else None,
        "updated_at": user.updated_at.isoformat() + "Z" if user.updated_at else None,
    }
