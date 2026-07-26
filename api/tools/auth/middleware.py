from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from db.engine import async_engine, async_session_factory
from db.users import get_session_by_id, get_user_by_id, is_user_locked, touch_session
from tools.auth.session_cookie import read_session_token, session_still_valid

AUTH_PUBLIC_PATHS = {
    "/auth/status",
    "/auth/setup",
    "/auth/login",
    "/auth/local-reset-owner",
}

MANAGEMENT_PREFIXES = (
    "/gateway/",
    "/video-tools/",
    "/doc-tools/",
    "/image-tools/",
    "/agent-resources/",
    "/settings/",
)


def needs_console_auth(path: str) -> bool:
    if path == "/healthz":
        return False
    if path == "/v1" or path.startswith("/v1/"):
        return False
    if path.startswith("/assets/"):
        return False
    if path in AUTH_PUBLIC_PATHS:
        return False
    if path.startswith("/auth/"):
        return True
    for prefix in MANAGEMENT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class ConsoleAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not needs_console_auth(path):
            return await call_next(request)

        token = read_session_token(request)
        if not token:
            return JSONResponse(status_code=401, content={"detail": "未登录或会话已失效"})

        async with async_session_factory(async_engine) as session:
            row = await get_session_by_id(session, token)
            if not row or not session_still_valid(row):
                return JSONResponse(
                    status_code=401, content={"detail": "未登录或会话已失效"}
                )
            session_id = str(row.id)
            user_id = int(row.user_id)
            user = await get_user_by_id(session, user_id)
            if not user or user.disabled or is_user_locked(user):
                return JSONResponse(
                    status_code=401, content={"detail": "未登录或会话已失效"}
                )
            try:
                await touch_session(session, session_id)
            except Exception:
                pass
            request.state.auth_user_id = user_id
            request.state.auth_session_id = session_id

        return await call_next(request)
