from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from db.client_keys import (
    add_client_key,
    consume_pending_gateway_key,
    delete_client_key,
    generate_gateway_api_key,
    get_client_api_key,
    get_client_api_key_by_app_id,
    get_client_api_key_meta,
    get_client_key_plain,
    register_pending_gateway_key,
    update_client_key_app_id,
)
from db.engine import get_session
from db.public_models import (
    create_public_model,
    delete_public_model,
    get_public_model,
    list_public_models,
    list_upstream_bindings,
    update_public_model,
)
from db.upstreams import (
    create_upstream,
    delete_upstream,
    get_upstream,
    get_upstream_runtime,
    list_enabled_upstream_rows,
    list_upstreams,
    mask_api_key,
    update_upstream,
)
from tools.gateway.schemas import (
    EmbeddingCapabilityProbeRequest,
    ModelCapabilityProbeModelsCustomRequest,
    ModelCapabilityProbeRequest,
    RerankCapabilityProbeRequest,
    TokenSpeedTestRequest,
)
from tools.gateway.services.capability_probe import probe_model_capabilities
from tools.gateway.services.embedding_probe import probe_embedding_similarity
from tools.gateway.services.rerank_probe import probe_rerank
from tools.gateway.services.token_speed_test import test_token_speed
from tools.gateway.services.upstream_client import (
    UpstreamRuntimeConfig,
    upstream_auth_headers,
    upstream_runtime_from_row,
)

router = APIRouter(prefix="/gateway/admin", tags=["gateway-admin"])


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def read_request_json(request: Request) -> Any:
    try:
        return await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from None


def _upstream_option_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row.get("name") or f"upstream-{row['id']}",
        "base_url": row.get("base_url"),
    }


def _route_bindings_summary(routes: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for route in routes:
        if not route.get("enabled", True):
            continue
        upstream_name = route.get("upstream_name") or f"源{route.get('upstream_id')}"
        parts.append(f"{upstream_name}/{route.get('upstream_model')}")
    return " + ".join(parts) if parts else "—"


def _sort_model_ids(model_ids: list[str]) -> list[str]:
    return sorted(model_ids, key=str.casefold)


async def _fetch_models_from_config(cfg: UpstreamRuntimeConfig) -> list[str]:
    try:
        async with httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            trust_env=cfg.trust_env,
        ) as client:
            resp = await client.get(
                "/models",
                headers=upstream_auth_headers(cfg.api_key),
            )
        if resp.is_error:
            return []
        payload = resp.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        ids: list[str] = []
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
        return _sort_model_ids(ids)
    except (httpx.HTTPError, ValueError, TypeError):
        return []


_MODELS_CACHE_TTL_SECONDS = 300.0
_upstream_models_cache: dict[int, tuple[float, list[str]]] = {}
_custom_models_cache: dict[str, tuple[float, list[str]]] = {}


def _custom_models_cache_key(uri: str, api_key: str) -> str:
    raw = f"{uri.strip()}\0{api_key}".encode()
    return hashlib.sha256(raw).hexdigest()


async def _get_upstream_models_cached(session: AsyncSession, upstream_id: int) -> tuple[list[str], bool]:
    now = time.monotonic()
    cached = _upstream_models_cache.get(upstream_id)
    if cached is not None and (now - cached[0]) < _MODELS_CACHE_TTL_SECONDS:
        return cached[1], True

    row = await get_upstream_runtime(session, upstream_id)
    if not row:
        raise HTTPException(status_code=400, detail="upstream not found")
    if not row.get("enabled"):
        raise HTTPException(status_code=400, detail="upstream is disabled")

    cfg = upstream_runtime_from_row(row)
    models = await _fetch_models_from_config(cfg) if cfg else []
    _upstream_models_cache[upstream_id] = (now, models)
    return models, False


async def _get_custom_models_cached(uri: str, api_key: str) -> tuple[list[str], bool]:
    cache_key = _custom_models_cache_key(uri, api_key)
    now = time.monotonic()
    cached = _custom_models_cache.get(cache_key)
    if cached is not None and (now - cached[0]) < _MODELS_CACHE_TTL_SECONDS:
        return cached[1], True

    cfg = UpstreamRuntimeConfig(base_url=uri.strip(), api_key=api_key.strip(), timeout_seconds=60.0, trust_env=False)
    models = await _fetch_models_from_config(cfg)
    _custom_models_cache[cache_key] = (now, models)
    return models, False


async def _build_upstream_config_for_save(
    session: AsyncSession,
    body: dict[str, Any],
    *,
    upstream_id: int | None = None,
) -> UpstreamRuntimeConfig:
    if upstream_id is not None:
        row = await get_upstream_runtime(session, upstream_id)
        if not row:
            raise HTTPException(status_code=404, detail="upstream not found")
        base_url = str(body.get("base_url") if "base_url" in body else row.get("base_url") or "").strip()
        if "api_key" in body and str(body.get("api_key") or "").strip():
            api_key = str(body.get("api_key") or "").strip()
        else:
            api_key = str(row.get("api_key") or "")
        trust_env = bool(body.get("trust_env")) if "trust_env" in body else bool(row.get("trust_env"))
        timeout_seconds = (
            float(body.get("timeout_seconds"))
            if body.get("timeout_seconds") is not None
            else float(row.get("timeout_seconds") or 60.0)
        )
    else:
        base_url = str(body.get("base_url") or "").strip()
        api_key = str(body.get("api_key") or "").strip()
        trust_env = bool(body.get("trust_env", False))
        timeout_seconds = float(body.get("timeout_seconds") or 60.0)

    if not base_url:
        raise HTTPException(status_code=400, detail="base_url is required")

    return UpstreamRuntimeConfig(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        trust_env=trust_env,
    )


async def _runtime_config_from_test_body(session: AsyncSession, body: dict[str, Any]) -> UpstreamRuntimeConfig:
    raw_id = body.get("id")
    upstream_id: int | None = None
    if raw_id is not None and str(raw_id).strip() != "":
        upstream_id = int(raw_id)
    return await _build_upstream_config_for_save(session, body, upstream_id=upstream_id)


async def _verify_upstream_connectivity(cfg: UpstreamRuntimeConfig) -> None:
    try:
        async with httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            trust_env=cfg.trust_env,
        ) as client:
            resp = await client.get(
                "/models",
                headers=upstream_auth_headers(cfg.api_key),
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="连通性测试失败：请求超时") from None
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"连通性测试失败：{exc}") from exc

    if resp.is_error:
        detail = f"连通性测试失败：上游返回 HTTP {resp.status_code}"
        try:
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("error"):
                err = payload["error"]
                if isinstance(err, dict) and err.get("message"):
                    detail = f"连通性测试失败：{err['message']}"
        except ValueError:
            text = (resp.text or "").strip()
            if text:
                detail = f"连通性测试失败：{text[:200]}"
        raise HTTPException(status_code=400, detail=detail)


@router.get("/client-info")
async def admin_client_info(
    request: Request,
    session: AsyncSession = Depends(get_session),
    app_id: str | None = Query(default=None),
) -> JSONResponse:
    base = str(request.base_url).rstrip("/")
    aid = str(app_id or "").strip()
    if aid:
        key = await get_client_api_key_by_app_id(session, aid)
        if key is None:
            raise HTTPException(status_code=404, detail=f"未找到 app_id={aid} 对应的 API Key")
    else:
        key = await get_client_api_key(session)
    return JSONResponse(content={
        "gateway_base_url": base,
        "gateway_api_key": key,
        "app_id": aid or None,
        "v1_models_url": f"{base}/v1/models",
        "v1_chat_completions_url": f"{base}/v1/chat/completions",
    })


@router.get("/gateway-client-keys")
async def admin_list_gateway_client_keys(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    return JSONResponse(content=await get_client_api_key_meta(session))


@router.get("/gateway-client-keys/{key_id}")
async def admin_get_client_key_plain(key_id: int, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    plain = await get_client_key_plain(session, key_id)
    if plain is None:
        raise HTTPException(status_code=404, detail="key not found")
    return JSONResponse(content={"id": key_id, "api_key": plain})


@router.post("/gateway-client-keys/generate")
async def admin_generate_gateway_client_key(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    key = generate_gateway_api_key()
    await register_pending_gateway_key(session, key)
    return JSONResponse(content={"gateway_api_key": key})


@router.post("/gateway-client-keys")
async def admin_add_client_key(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    app_id = str(raw.get("app_id") or "").strip()
    key = str(raw.get("gateway_api_key") or "").strip()
    if not app_id:
        raise HTTPException(status_code=400, detail="app_id is required")
    if not key:
        raise HTTPException(status_code=400, detail="gateway_api_key is required; use generate first")
    if not await consume_pending_gateway_key(session, key):
        raise HTTPException(status_code=400, detail="invalid or expired generated key; click regenerate")
    try:
        new_id = await add_client_key(session, key, app_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    plain = await get_client_key_plain(session, new_id) or key
    meta = await get_client_api_key_meta(session)
    return JSONResponse(status_code=201, content={
        "id": new_id,
        "api_key": plain,
        "api_key_masked": mask_api_key(plain),
        **meta,
    })


@router.api_route("/gateway-client-keys/{key_id}", methods=["PATCH", "POST"])
async def admin_patch_client_key(key_id: int, request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    if "app_id" not in raw:
        raise HTTPException(status_code=400, detail="app_id is required")
    try:
        await update_client_key_app_id(session, key_id, str(raw.get("app_id") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="key not found") from exc
    meta = await get_client_api_key_meta(session)
    return JSONResponse(content=meta)


@router.delete("/gateway-client-keys/{key_id}")
async def admin_delete_client_key(key_id: int, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    try:
        await delete_client_key(session, key_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="key not found") from exc
    meta = await get_client_api_key_meta(session)
    return JSONResponse(content=meta)


@router.get("/upstreams")
async def admin_list_upstreams(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    return JSONResponse(content={"items": await list_upstreams(session)})


@router.get("/upstreams/{upstream_id}")
async def admin_get_upstream(upstream_id: int, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    row = await get_upstream(session, upstream_id)
    if not row:
        raise HTTPException(status_code=404, detail="upstream not found")
    return JSONResponse(content=row)


@router.post("/upstreams")
async def admin_create_upstream(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    name = str(body.get("name") or "").strip()
    base_url = str(body.get("base_url") or "").strip()
    api_key = str(body.get("api_key") or "").strip()
    if not name or not base_url:
        raise HTTPException(status_code=400, detail="name, base_url are required")
    cfg = await _build_upstream_config_for_save(session, body)
    await _verify_upstream_connectivity(cfg)
    new_id = await create_upstream(
        session,
        name=name,
        base_url=base_url,
        api_key=api_key,
        trust_env=bool(body.get("trust_env", False)),
        timeout_seconds=float(body.get("timeout_seconds") or 60.0),
        enabled=bool(body.get("enabled", True)),
    )
    row = await get_upstream(session, new_id)
    return JSONResponse(status_code=201, content=row)


# Must be registered before /upstreams/{upstream_id} so "test" is not parsed as an int id.
@router.post("/upstreams/test")
async def admin_test_upstream(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    raw = await read_request_json(request)
    body = raw if isinstance(raw, dict) else {}
    cfg = await _runtime_config_from_test_body(session, body)
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            trust_env=cfg.trust_env,
        ) as client:
            resp = await client.get(
                "/models",
                headers=upstream_auth_headers(cfg.api_key),
            )
    except httpx.TimeoutException:
        return JSONResponse(status_code=200, content={
            "ok": False,
            "error": "timeout",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        })
    except httpx.HTTPError as exc:
        return JSONResponse(status_code=200, content={
            "ok": False,
            "error": str(exc),
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        })
    latency_ms = int((time.perf_counter() - t0) * 1000)
    preview: Any
    try:
        preview = resp.json()
    except ValueError:
        preview = {"raw": (resp.text or "")[:800]}
    return JSONResponse(status_code=200, content={
        "ok": not resp.is_error,
        "upstream_status_code": resp.status_code,
        "latency_ms": latency_ms,
        "body": preview,
    })


@router.api_route("/upstreams/{upstream_id}", methods=["PATCH", "POST"])
async def admin_patch_upstream(request: Request, upstream_id: int, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    cfg = await _build_upstream_config_for_save(session, body, upstream_id=upstream_id)
    await _verify_upstream_connectivity(cfg)
    ok = await update_upstream(
        session, upstream_id,
        name=body.get("name") if "name" in body else None,
        base_url=body.get("base_url") if "base_url" in body else None,
        api_key=body.get("api_key") if "api_key" in body else None,
        trust_env=body.get("trust_env") if "trust_env" in body else None,
        timeout_seconds=body.get("timeout_seconds") if "timeout_seconds" in body else None,
        enabled=body.get("enabled") if "enabled" in body else None,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="upstream not found")
    _upstream_models_cache.pop(upstream_id, None)
    row = await get_upstream(session, upstream_id)
    return JSONResponse(content=row)


@router.get("/upstreams/{upstream_id}/bindings")
async def admin_list_upstream_bindings(
    upstream_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    row = await get_upstream(session, upstream_id)
    if not row:
        raise HTTPException(status_code=404, detail="upstream not found")
    items = await list_upstream_bindings(session, upstream_id)
    return JSONResponse(content={"upstream_id": upstream_id, "items": items})


@router.delete("/upstreams/{upstream_id}")
async def admin_delete_upstream(upstream_id: int, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    try:
        ok = await delete_upstream(session, upstream_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="upstream not found")
    return JSONResponse(content={"ok": True, "deleted_id": upstream_id})


@router.get("/upstreams/{upstream_id}/models")
async def admin_list_upstream_models(
    upstream_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    models, from_cache = await _get_upstream_models_cached(session, upstream_id)
    return JSONResponse(content={"upstream_id": upstream_id, "models": models, "cached": from_cache})


@router.get("/public-models")
async def admin_list_public_models(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    items = await list_public_models(session)
    for item in items:
        item["bindings_summary"] = _route_bindings_summary(item.get("routes") or [])
    return JSONResponse(content={"items": items})


@router.get("/public-models/{model_id}")
async def admin_get_public_model(model_id: int, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    row = await get_public_model(session, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="public model not found")
    row["bindings_summary"] = _route_bindings_summary(row.get("routes") or [])
    return JSONResponse(content=row)


@router.post("/public-models")
async def admin_create_public_model(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    routes = body.get("routes")
    if not isinstance(routes, list):
        raise HTTPException(status_code=400, detail="routes must be an array")
    try:
        new_id = await create_public_model(
            session,
            name=str(body.get("name") or ""),
            enabled=bool(body.get("enabled", True)),
            routes=routes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = await get_public_model(session, new_id)
    assert row is not None
    row["bindings_summary"] = _route_bindings_summary(row.get("routes") or [])
    return JSONResponse(status_code=201, content=row)


@router.api_route("/public-models/{model_id}", methods=["PATCH", "POST"])
async def admin_patch_public_model(
    request: Request,
    model_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    routes = body.get("routes") if "routes" in body else None
    if routes is not None and not isinstance(routes, list):
        raise HTTPException(status_code=400, detail="routes must be an array")
    try:
        ok = await update_public_model(
            session,
            model_id,
            name=body.get("name") if "name" in body else None,
            enabled=body.get("enabled") if "enabled" in body else None,
            routes=routes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="public model not found")
    row = await get_public_model(session, model_id)
    assert row is not None
    row["bindings_summary"] = _route_bindings_summary(row.get("routes") or [])
    return JSONResponse(content=row)


@router.delete("/public-models/{model_id}")
async def admin_delete_public_model(model_id: int, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    ok = await delete_public_model(session, model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="public model not found")
    return JSONResponse(content={"ok": True, "deleted_id": model_id})


@router.get("/model-capability-probe/options")
async def admin_model_capability_probe_options(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    rows = await list_enabled_upstream_rows(session)
    upstreams = [_upstream_option_public(row) for row in rows]
    return JSONResponse(content={"upstreams": upstreams})


@router.get("/model-capability-probe/models")
async def admin_model_capability_probe_models(
    upstream_id: int = Query(..., ge=1),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    models, from_cache = await _get_upstream_models_cached(session, upstream_id)
    return JSONResponse(content={"upstream_id": upstream_id, "models": models, "cached": from_cache})


@router.post("/model-capability-probe/models/custom")
async def admin_model_capability_probe_models_custom(request: Request) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        body = ModelCapabilityProbeModelsCustomRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from None
    models, from_cache = await _get_custom_models_cached(body.uri.strip(), body.api_key.strip())
    return JSONResponse(content={"models": models, "cached": from_cache})


async def _resolve_probe_credentials(
    session: AsyncSession,
    body: ModelCapabilityProbeRequest | EmbeddingCapabilityProbeRequest | RerankCapabilityProbeRequest,
) -> tuple[str, str, str]:
    if body.mode == "upstream":
        row = await get_upstream_runtime(session, int(body.upstream_id))
        if not row:
            raise HTTPException(status_code=400, detail="upstream not found")
        if not row.get("enabled"):
            raise HTTPException(status_code=400, detail="upstream is disabled")
        uri = str(row.get("base_url") or "").strip()
        api_key = str(row.get("api_key") or "").strip()
        if not uri:
            raise HTTPException(status_code=400, detail="incomplete upstream configuration")
        return uri, api_key, str(body.model).strip()
    uri = str(body.uri).strip()
    api_key = str(body.api_key).strip()
    return uri, api_key, str(body.model).strip()


async def _resolve_speed_test_credentials(
    session: AsyncSession,
    body: TokenSpeedTestRequest,
) -> tuple[str, str, str]:
    if body.mode == "upstream":
        row = await get_upstream_runtime(session, int(body.upstream_id))
        if not row:
            raise HTTPException(status_code=400, detail="upstream not found")
        if not row.get("enabled"):
            raise HTTPException(status_code=400, detail="upstream is disabled")
        uri = str(row.get("base_url") or "").strip()
        api_key = str(row.get("api_key") or "").strip()
        if not uri:
            raise HTTPException(status_code=400, detail="incomplete upstream configuration")
        return uri, api_key, str(body.model).strip()
    uri = str(body.uri).strip()
    api_key = str(body.api_key).strip()
    return uri, api_key, str(body.model).strip()


@router.post("/token-speed-test")
async def admin_token_speed_test(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        body = TokenSpeedTestRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from None

    uri, api_key, model = await _resolve_speed_test_credentials(session, body)
    t0 = time.perf_counter()
    report = await asyncio.to_thread(
        test_token_speed, uri, api_key, model,
        timeout=body.timeout, max_tokens=body.max_tokens,
    )
    report["total_elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return JSONResponse(content=report)


@router.post("/token-speed-test/stream")
async def admin_token_speed_test_stream(request: Request, session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        body = TokenSpeedTestRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from None

    uri, api_key, model = await _resolve_speed_test_credentials(session, body)

    async def event_stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_progress(stage: str, message: str, percent: int, extra: dict[str, Any] | None = None) -> None:
            data: dict[str, Any] = {"stage": stage, "message": message, "percent": percent}
            if extra:
                data.update(extra)
            loop.call_soon_threadsafe(queue.put_nowait, ("progress", data))

        async def run_job() -> None:
            t0 = time.perf_counter()
            try:
                report = await asyncio.to_thread(
                    test_token_speed,
                    uri,
                    api_key,
                    model,
                    timeout=body.timeout,
                    max_tokens=body.max_tokens,
                    on_progress=on_progress,
                )
                report["total_elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
                await queue.put(("done", report))
            except Exception as exc:
                await queue.put(("error", {"detail": str(exc)}))
            finally:
                await queue.put(("__close__", {}))

        task = asyncio.create_task(run_job())
        try:
            while True:
                event, data = await queue.get()
                if event == "__close__":
                    break
                yield _sse_event(event, data)
                if event in ("done", "error"):
                    break
        finally:
            if not task.done():
                task.cancel()
                with asyncio.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/model-capability-probe")
async def admin_model_capability_probe(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        body = ModelCapabilityProbeRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from None

    uri, api_key, model = await _resolve_probe_credentials(session, body)
    t0 = time.perf_counter()
    report = await asyncio.to_thread(
        probe_model_capabilities, uri, api_key, model,
        timeout=body.timeout, max_tokens=body.max_tokens,
    )
    report["total_elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return JSONResponse(content=report)


@router.post("/embedding-capability-probe")
async def admin_embedding_capability_probe(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        body = EmbeddingCapabilityProbeRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from None

    uri, api_key, model = await _resolve_probe_credentials(session, body)
    t0 = time.perf_counter()
    report = await asyncio.to_thread(
        probe_embedding_similarity,
        uri,
        api_key,
        model,
        body.text_a.strip(),
        body.text_b.strip(),
        timeout=body.timeout,
    )
    report["total_elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return JSONResponse(content=report)


@router.post("/rerank-capability-probe")
async def admin_rerank_capability_probe(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        body = RerankCapabilityProbeRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from None

    uri, api_key, model = await _resolve_probe_credentials(session, body)
    t0 = time.perf_counter()
    report = await asyncio.to_thread(
        probe_rerank,
        uri,
        api_key,
        model,
        body.query.strip(),
        list(body.documents),
        timeout=body.timeout,
    )
    report["total_elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return JSONResponse(content=report)
