from __future__ import annotations

import copy
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.upstreams import list_failover_upstream_rows
from dependencies import resolve_gateway_client
from errors import (
    normalize_upstream_error,
    openai_error_response,
    upstream_timeout_error,
    upstream_unavailable_error,
)
from tools.gateway.services.log_pipeline import schedule_log_event
from tools.gateway.services.upstream_client import (
    UpstreamClient,
    upstream_runtime_from_row,
    try_upstream_rows,
)

router = APIRouter(prefix="/v1", tags=["gateway"])

DEFAULT_LOG_SESSION_ID = "default"


async def read_request_json(request: Request) -> Any:
    try:
        return await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from None


def _resolve_session_and_upstream_body(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    raw = body.get("session_id")
    sid = str(raw).strip() if raw is not None and str(raw).strip() else DEFAULT_LOG_SESSION_ID
    upstream = {k: v for k, v in body.items() if k != "session_id"}
    return sid, upstream


def no_upstream_response() -> JSONResponse:
    return openai_error_response(
        message="No enabled default upstream configured",
        status_code=503,
        error_type="upstream_error",
        code="upstream_not_configured",
    )


def parse_response_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {
            "error": {
                "message": "Upstream returned non-JSON response",
                "type": "upstream_error",
                "param": None,
                "code": "invalid_upstream_response",
            }
        }


@router.get("/models")
async def list_models(
    request: Request,
    app_id: str = Depends(resolve_gateway_client),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    rows = await list_failover_upstream_rows(session)
    if not rows:
        return no_upstream_response()

    try:
        upstream_response, _client = await try_upstream_rows(rows, lambda c: c.list_models())
    except httpx.TimeoutException:
        return upstream_timeout_error()
    except httpx.HTTPError:
        return upstream_unavailable_error()

    payload = parse_response_json(upstream_response)
    if upstream_response.is_error:
        return normalize_upstream_error(upstream_response.status_code, payload)
    return JSONResponse(status_code=upstream_response.status_code, content=payload)


@router.post("/chat/completions", response_model=None)
async def create_chat_completions(
    request: Request,
    app_id: str = Depends(resolve_gateway_client),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse | StreamingResponse:
    client_ip = request.client.host if request.client else None

    rows = await list_failover_upstream_rows(session)
    if not rows:
        return no_upstream_response()

    start = time.perf_counter()
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    session_id, upstream_body = _resolve_session_and_upstream_body(body)
    model = upstream_body.get("model")
    stream = bool(upstream_body.get("stream", False))

    if stream:
        client: UpstreamClient | None = None
        upstream_response: httpx.Response | None = None
        stream_iter: AsyncIterator[bytes] | None = None
        last_transport_error: Exception | None = None

        for row in rows:
            cfg = upstream_runtime_from_row(row)
            if not cfg:
                continue
            client = UpstreamClient(cfg)
            try:
                upstream_response, stream_iter = await client.chat_completions_stream(upstream_body)
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                await client.close()
                last_transport_error = exc
                continue

            if upstream_response.is_error:
                payload = parse_response_json(upstream_response)
                return normalize_upstream_error(upstream_response.status_code, payload)
            break
        else:
            if isinstance(last_transport_error, httpx.TimeoutException):
                return upstream_timeout_error()
            return upstream_unavailable_error()

        async def wrapped_stream() -> AsyncIterator[bytes]:
            response_chunks: list[str] = []
            try:
                async for chunk in stream_iter:
                    response_chunks.append(chunk.decode("utf-8", errors="ignore"))
                    yield chunk
            finally:
                await upstream_response.aclose()
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                gw_path = "/v1/chat/completions"
                log_tasks = getattr(request.app.state, "_log_tasks", set())
                schedule_log_event(
                    session=session,
                    event=copy.deepcopy({
                        "path": client.logged_upstream_url(gw_path),
                        "model": model,
                        "status_code": upstream_response.status_code,
                        "latency_ms": elapsed_ms,
                        "client_ip": client_ip,
                        "input_tokens": None,
                        "output_tokens": None,
                        "total_tokens": None,
                        "request_body": upstream_body,
                        "response_body": "".join(response_chunks),
                        "session_id": session_id,
                        "app_id": app_id,
                    }),
                    stream_body="".join(response_chunks),
                    request_body=copy.deepcopy(upstream_body),
                    log_tasks=log_tasks,
                )

        return StreamingResponse(
            wrapped_stream(),
            media_type=upstream_response.headers.get("content-type", "text/event-stream"),
        )

    try:
        upstream_response, client = await try_upstream_rows(
            rows, lambda c: c.chat_completions(upstream_body)
        )
    except httpx.TimeoutException:
        return upstream_timeout_error()
    except httpx.HTTPError:
        return upstream_unavailable_error()

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    payload = parse_response_json(upstream_response)
    usage = payload.get("usage") if isinstance(payload, dict) else {}
    input_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    output_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    gw_path = "/v1/chat/completions"

    log_tasks = getattr(request.app.state, "_log_tasks", set())
    schedule_log_event(
        session=session,
        event=copy.deepcopy({
            "path": client.logged_upstream_url(gw_path),
            "model": model,
            "status_code": upstream_response.status_code,
            "latency_ms": elapsed_ms,
            "client_ip": client_ip,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "request_body": upstream_body,
            "response_body": payload,
            "session_id": session_id,
            "app_id": app_id,
        }),
        log_tasks=log_tasks,
    )

    if upstream_response.is_error:
        return normalize_upstream_error(upstream_response.status_code, payload)
    return JSONResponse(status_code=upstream_response.status_code, content=payload)
