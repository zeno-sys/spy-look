from __future__ import annotations

from fastapi import Header, HTTPException

from .usage import client_api_key_is_valid


def verify_gateway_key(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise_auth_error("Missing or invalid Authorization header")

    provided_key = authorization.removeprefix("Bearer ").strip()
    if not client_api_key_is_valid(provided_key):
        raise_auth_error("Invalid API key")


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
