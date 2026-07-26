from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.models import SpyLookUser
from db.users import ROLE_OWNER, get_session_by_id, get_user_by_id, is_user_locked
from tools.auth.session_cookie import read_session_token, session_still_valid


@dataclass
class AuthContext:
    user: SpyLookUser
    session_id: str


async def get_optional_auth(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthContext | None:
    token = read_session_token(request)
    if not token:
        return None
    row = await get_session_by_id(session, token)
    if not row or not session_still_valid(row):
        return None
    user = await get_user_by_id(session, row.user_id)
    if not user or user.disabled or is_user_locked(user):
        return None
    return AuthContext(user=user, session_id=row.id)


async def require_auth(
    ctx: AuthContext | None = Depends(get_optional_auth),
) -> AuthContext:
    if ctx is None:
        raise HTTPException(status_code=401, detail="未登录或会话已失效")
    return ctx


async def require_owner(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
    if ctx.user.role != ROLE_OWNER:
        raise HTTPException(status_code=403, detail="需要 Owner 权限")
    return ctx
