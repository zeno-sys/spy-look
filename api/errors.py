from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def openai_error_response(
    *,
    message: str,
    status_code: int,
    error_type: str = "gateway_error",
    code: str | None = None,
    param: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "param": param,
                "code": code,
            }
        },
    )


def upstream_timeout_error() -> JSONResponse:
    return openai_error_response(
        message="Upstream request timeout",
        status_code=504,
        error_type="timeout_error",
        code="upstream_timeout",
    )


def upstream_unavailable_error() -> JSONResponse:
    return openai_error_response(
        message="Failed to connect upstream",
        status_code=502,
        error_type="upstream_error",
        code="upstream_unavailable",
    )


def normalize_upstream_error(status_code: int, payload: Any) -> JSONResponse:
    if isinstance(payload, dict) and "error" in payload:
        return JSONResponse(status_code=status_code, content=payload)
    return openai_error_response(
        message="Upstream request failed",
        status_code=status_code,
        error_type="upstream_error",
        code="upstream_error",
    )
