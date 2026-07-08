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


def model_not_found_error(model: str) -> JSONResponse:
    return openai_error_response(
        message=f"The model `{model}` does not exist",
        status_code=404,
        error_type="invalid_request_error",
        code="model_not_found",
        param="model",
    )


def no_available_route_error() -> JSONResponse:
    return openai_error_response(
        message="No available route for the requested model",
        status_code=503,
        error_type="upstream_error",
        code="no_available_route",
    )


def no_public_models_response() -> JSONResponse:
    return openai_error_response(
        message="No enabled public models configured",
        status_code=503,
        error_type="upstream_error",
        code="upstream_not_configured",
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
