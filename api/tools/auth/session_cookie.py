from __future__ import annotations

from datetime import datetime

from fastapi import Request, Response

from db.models import SpyLookSession
from db.users import SESSION_DAYS_REMEMBER

COOKIE_NAME = "spy_look_session"


def cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https"


def set_session_cookie(
    response: Response, request: Request, session_row: SpyLookSession
) -> None:
    kwargs: dict = {
        "key": COOKIE_NAME,
        "value": session_row.id,
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "secure": cookie_secure(request),
    }
    if session_row.remember:
        max_age = SESSION_DAYS_REMEMBER * 24 * 60 * 60
        kwargs["max_age"] = max_age
    response.set_cookie(**kwargs)


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=cookie_secure(request),
        httponly=True,
        samesite="lax",
    )


def read_session_token(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    text = str(token).strip()
    return text or None


def is_loopback(request: Request) -> bool:
    """仅本机直连可用。peer 必须是 loopback，且 Host 也必须是本机名（防止反代伪造）。"""
    client = request.client
    if client is None:
        return False
    peer = (client.host or "").strip().lower()
    if peer not in {"127.0.0.1", "::1", "localhost"}:
        return False
    req_host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if req_host and req_host not in {"127.0.0.1", "localhost", "::1"}:
        return False
    return True


def session_still_valid(row: SpyLookSession) -> bool:
    return row.expires_at > datetime.utcnow()
