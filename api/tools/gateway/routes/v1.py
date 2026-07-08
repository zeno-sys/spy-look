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
from db.public_models import get_public_model_by_name, list_enabled_routes_for_model, list_public_model_ids
from dependencies import resolve_gateway_client
from errors import (
    model_not_found_error,
    no_available_route_error,
    no_public_models_response,
    normalize_upstream_error,
    upstream_timeout_error,
    upstream_unavailable_error,
)
from tools.gateway.services.log_pipeline import schedule_log_event
from tools.gateway.services.model_router import pick_route_index, resolve_session_id, try_routes_with_sticky_failover
from tools.gateway.services.upstream_client import UpstreamClient, upstream_runtime_from_row

router = APIRouter(prefix="/v1", tags=["gateway"])


async def read_request_json(request: Request) -> Any:
    try:
        return await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from None


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
    model_ids = await list_public_model_ids(session)
    if not model_ids:
        return no_public_models_response()

    payload = {
        "object": "list",
        "data": [
            {
                "id": name,
                "object": "model",
                "created": 0,
                "owned_by": "spy-look",
            }
            for name in model_ids
        ],
    }
    return JSONResponse(status_code=200, content=payload)


@router.post("/chat/completions", response_model=None)
async def create_chat_completions(
    request: Request,
    app_id: str = Depends(resolve_gateway_client),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse | StreamingResponse:
    client_ip = request.client.host if request.client else None
    session_id = resolve_session_id(request)

    start = time.perf_counter()
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    public_model = body.get("model")
    if not public_model or not str(public_model).strip():
        raise HTTPException(status_code=400, detail="model is required")

    public_model = str(public_model).strip()
    model_row = await get_public_model_by_name(session, public_model)
    if not model_row or not model_row.enabled:
        return model_not_found_error(public_model)

    _, routes = await list_enabled_routes_for_model(session, public_model)
    if not routes:
        return no_available_route_error()

    upstream_body = copy.deepcopy(body)
    stream = bool(upstream_body.get("stream", False))
    start_idx = pick_route_index(len(routes), session_id)

    if stream:
        client: UpstreamClient | None = None
        upstream_response: httpx.Response | None = None
        stream_iter: AsyncIterator[bytes] | None = None
        last_transport_error: Exception | None = None
        selected_upstream_model: str | None = None

        for offset in range(len(routes)):
            route = routes[(start_idx + offset) % len(routes)]
            cfg = upstream_runtime_from_row(route.upstream_row)
            if not cfg:
                continue
            client = UpstreamClient(cfg)
            payload = {**upstream_body, "model": route.upstream_model}
            try:
                upstream_response, stream_iter = await client.chat_completions_stream(payload)
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                await client.close()
                last_transport_error = exc
                continue

            if upstream_response.is_error:
                parsed = parse_response_json(upstream_response)
                return normalize_upstream_error(upstream_response.status_code, parsed)
            selected_upstream_model = route.upstream_model
            break
        else:
            if isinstance(last_transport_error, httpx.TimeoutException):
                return upstream_timeout_error()
            return upstream_unavailable_error()

        assert client is not None and upstream_response is not None and stream_iter is not None

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
                    event=copy.deepcopy({
                        "path": client.logged_upstream_url(gw_path),
                        "model": public_model,
                        "upstream_model": selected_upstream_model,
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
        upstream_response, client, route = await try_routes_with_sticky_failover(
            routes,
            session_id,
            lambda c, payload: c.chat_completions(payload),
            upstream_body,
        )
    except httpx.TimeoutException:
        return upstream_timeout_error()
    except httpx.HTTPError:
        return upstream_unavailable_error()
    except RuntimeError:
        return no_available_route_error()

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    payload = parse_response_json(upstream_response)
    usage = payload.get("usage") if isinstance(payload, dict) else {}
    input_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    output_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    gw_path = "/v1/chat/completions"

    log_tasks = getattr(request.app.state, "_log_tasks", set())
    schedule_log_event(
        event=copy.deepcopy({
            "path": client.logged_upstream_url(gw_path),
            "model": public_model,
            "upstream_model": route.upstream_model,
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
