from __future__ import annotations

from fastapi import Header, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from db.client_keys import resolve_app_id_by_api_key


async def resolve_gateway_client(
    authorization: str | None = Header(default=None),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise_auth_error("Missing or invalid Authorization header")

    provided_key = authorization.removeprefix("Bearer ").strip()
    from db.engine import async_session_factory, async_engine
    async with async_session_factory(async_engine) as session:
        app_id = await resolve_app_id_by_api_key(session, provided_key)

    if not app_id:
        raise_auth_error("Invalid API key")
    return app_id


def raise_auth_error(message: str) -> None:
    raise HTTPException(
        status_code=401,
        detail={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_api_key",
            }
        },
    )
