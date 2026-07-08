from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx
from fastapi import Request

from db.public_models import ResolvedModelRoute
from tools.gateway.services.upstream_client import UpstreamClient, upstream_runtime_from_row

T = TypeVar("T")

DEFAULT_LOG_SESSION_ID = "default"


def resolve_session_id(request: Request) -> str:
    raw = request.headers.get("X-Session-Id")
    sid = str(raw).strip() if raw else ""
    return sid or DEFAULT_LOG_SESSION_ID


def pick_route_index(route_count: int, session_id: str) -> int:
    if route_count <= 0:
        return 0
    digest = hashlib.sha256(session_id.encode()).digest()
    return int.from_bytes(digest[:8], "big") % route_count


async def try_routes_with_sticky_failover(
    routes: list[ResolvedModelRoute],
    session_id: str,
    call: Callable[[UpstreamClient, dict[str, Any]], Awaitable[T]],
    upstream_body: dict[str, Any],
) -> tuple[T, UpstreamClient, ResolvedModelRoute]:
    if not routes:
        raise RuntimeError("No routes available")

    start = pick_route_index(len(routes), session_id)
    last_error: Exception | None = None

    for offset in range(len(routes)):
        route = routes[(start + offset) % len(routes)]
        cfg = upstream_runtime_from_row(route.upstream_row)
        if not cfg:
            continue
        client = UpstreamClient(cfg)
        body = {**upstream_body, "model": route.upstream_model}
        try:
            result = await call(client, body)
            return result, client, route
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            await client.close()
            last_error = exc

    if last_error:
        raise last_error
    raise RuntimeError("No enabled upstream available")
