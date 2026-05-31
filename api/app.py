from __future__ import annotations

import time
from json import JSONDecodeError
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import verify_gateway_key
from .errors import (
    normalize_upstream_error,
    openai_error_response,
    upstream_timeout_error,
    upstream_unavailable_error,
)
from .upstream_client import UpstreamClient, UpstreamRuntimeConfig, upstream_runtime_from_row
from .usage import (
    add_client_key,
    create_upstream,
    delete_client_key,
    delete_log,
    delete_upstream,
    get_client_api_key,
    get_client_api_key_meta,
    get_client_key_plain,
    get_default_upstream_row,
    get_upstream,
    get_upstream_runtime,
    list_log_sessions,
    list_upstreams,
    log_event,
    mask_api_key,
    query_logs,
    set_default_upstream,
    setup_logging,
    update_upstream,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PACKAGE_ROOT / "web"

DEFAULT_LOG_SESSION_ID = "default"


async def read_request_json(request: Request) -> Any:
    try:
        return await request.json()
    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})",
        ) from None


def _resolve_session_and_upstream_body(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Gateway-only session_id for log isolation; strip before upstream."""
    raw = body.get("session_id")
    if raw is None:
        sid = DEFAULT_LOG_SESSION_ID
    else:
        text = str(raw).strip()
        sid = text if text else DEFAULT_LOG_SESSION_ID
    upstream = {k: v for k, v in body.items() if k != "session_id"}
    return sid, upstream


async def refresh_upstream_client(app: FastAPI) -> None:
    old = getattr(app.state, "upstream_client", None)
    row = get_default_upstream_row()
    cfg = upstream_runtime_from_row(row) if row else None
    if old is not None:
        await old.close()
    app.state.upstream_client = UpstreamClient(cfg) if cfg else None


def no_upstream_response() -> JSONResponse:
    return openai_error_response(
        message="No enabled default upstream configured",
        status_code=503,
        error_type="upstream_error",
        code="upstream_not_configured",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    row = get_default_upstream_row()
    cfg = upstream_runtime_from_row(row)
    app.state.upstream_client = UpstreamClient(cfg) if cfg else None
    try:
        yield
    finally:
        client = getattr(app.state, "upstream_client", None)
        if client is not None:
            await client.close()


app = FastAPI(title="Spy-Look", version="0.1.0", lifespan=lifespan)

app.mount("/css", StaticFiles(directory=WEB_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=WEB_DIR / "js"), name="js")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
async def index_page() -> FileResponse:
    """日志观测页（静态 HTML）。"""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/upstream-config", include_in_schema=False)
async def upstream_config_page() -> FileResponse:
    """上游连接配置管理页。"""
    return FileResponse(WEB_DIR / "upstream-config.html")


@app.get("/logs")
async def get_logs(
    path: str | None = Query(default=None),
    model: str | None = Query(default=None),
    client_ip: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    order_by: str = Query(default="created_at"),
    order_dir: str = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:  
    items = query_logs(
        path=path,
        model=model,
        client_ip=client_ip,
        session_id=session_id,
        start_time=start_time,
        end_time=end_time,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
        offset=offset,
    )
    return JSONResponse(content={"items": items, "limit": limit, "offset": offset})


@app.get("/logs/sessions")
async def get_log_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    items, total = list_log_sessions(limit=limit, offset=offset)
    return JSONResponse(
        content={"items": items, "total": total, "limit": limit, "offset": offset}
    )


@app.delete("/logs/{log_id}")
async def remove_log(log_id: int) -> JSONResponse:
    deleted = delete_log(log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="log not found")
    return JSONResponse(content={"ok": True, "deleted_id": log_id})


def _runtime_config_from_test_body(body: dict[str, Any]) -> UpstreamRuntimeConfig:
    raw_id = body.get("id")
    if raw_id is not None and str(raw_id).strip() != "":
        uid = int(raw_id)
        row = get_upstream_runtime(uid)
        if not row:
            raise HTTPException(status_code=404, detail="upstream not found")
        base_url = str(body.get("base_url") or row.get("base_url") or "").strip()
        api_key_raw = body.get("api_key")
        if api_key_raw is not None and str(api_key_raw).strip():
            api_key = str(api_key_raw).strip()
        else:
            api_key = str(row.get("api_key") or "")
        if body.get("trust_env") is None:
            trust_env = bool(row.get("trust_env"))
        else:
            trust_env = bool(body.get("trust_env"))
        if body.get("timeout_seconds") is None:
            timeout_seconds = float(row.get("timeout_seconds") or 60.0)
        else:
            timeout_seconds = float(body.get("timeout_seconds"))
        cfg = UpstreamRuntimeConfig(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            trust_env=trust_env,
        )
        if not cfg.base_url or not cfg.api_key:
            raise HTTPException(status_code=400, detail="incomplete upstream after merge")
        return cfg
    base_url = str(body.get("base_url") or "").strip()
    api_key = str(body.get("api_key") or "").strip()
    if not base_url or not api_key:
        raise HTTPException(
            status_code=400,
            detail="base_url and api_key are required when id is omitted",
        )
    return UpstreamRuntimeConfig(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=float(body.get("timeout_seconds") or 60.0),
        trust_env=bool(body.get("trust_env", False)),
    )


@app.post("/admin/upstreams/test")
async def admin_test_upstream(request: Request) -> JSONResponse:
    """测试与上游的连通性（GET /v1/models 等价的 /models）。"""
    raw = await read_request_json(request)
    body = raw if isinstance(raw, dict) else {}
    cfg = _runtime_config_from_test_body(body)
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            trust_env=cfg.trust_env,
        ) as client:
            resp = await client.get(
                "/models",
                headers={
                    "Authorization": f"Bearer {cfg.api_key}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": "timeout",
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": str(exc),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    preview: Any
    try:
        preview = resp.json()
    except ValueError:
        preview = {"raw": (resp.text or "")[:800]}
    return JSONResponse(
        status_code=200,
        content={
            "ok": not resp.is_error,
            "upstream_status_code": resp.status_code,
            "latency_ms": latency_ms,
            "body": preview,
        },
    )


@app.get("/admin/client-info")
async def admin_client_info(request: Request) -> JSONResponse:
    """供本机日志页展示：网关根 URL、`/v1/models` 与 `/v1/chat/completions` 等；`gateway_api_key` 为库中首条对外 Key 的完整值（便于复制示例；勿暴露在公网）。"""
    base = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={
            "gateway_base_url": base,
            "gateway_api_key": get_client_api_key(),
            "v1_models_url": f"{base}/v1/models",
            "v1_chat_completions_url": f"{base}/v1/chat/completions",
        }
    )


@app.get("/admin/gateway-client-keys")
async def admin_list_gateway_client_keys() -> JSONResponse:
    return JSONResponse(content=get_client_api_key_meta())


@app.get("/admin/gateway-client-keys/{key_id}")
async def admin_get_client_key_plain(key_id: int) -> JSONResponse:
    """供配置页「复制」拉取完整密钥（与 /admin 其它接口相同，勿暴露在公网）。"""
    plain = get_client_key_plain(key_id)
    if plain is None:
        raise HTTPException(status_code=404, detail="key not found")
    return JSONResponse(content={"id": key_id, "api_key": plain})


@app.post("/admin/gateway-client-keys")
async def admin_add_client_key(request: Request) -> JSONResponse:
    raw = await read_request_json(request)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    key = str(raw.get("gateway_api_key") or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="gateway_api_key is required")
    try:
        new_id = add_client_key(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    plain = get_client_key_plain(new_id) or key
    return JSONResponse(
        status_code=201,
        content={
            "id": new_id,
            "api_key": plain,
            "api_key_masked": mask_api_key(plain),
            **get_client_api_key_meta(),
        },
    )


@app.delete("/admin/gateway-client-keys/{key_id}")
async def admin_delete_client_key(key_id: int) -> JSONResponse:
    try:
        delete_client_key(key_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="key not found") from exc
    return JSONResponse(content=get_client_api_key_meta())


@app.get("/admin/upstreams")
async def admin_list_upstreams() -> JSONResponse:
    return JSONResponse(content={"items": list_upstreams()})


@app.get("/admin/upstreams/{upstream_id}")
async def admin_get_upstream(upstream_id: int) -> JSONResponse:
    row = get_upstream(upstream_id)
    if not row:
        raise HTTPException(status_code=404, detail="upstream not found")
    return JSONResponse(content=row)


@app.post("/admin/upstreams")
async def admin_create_upstream(request: Request) -> JSONResponse:
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    name = str(body.get("name") or "").strip()
    base_url = str(body.get("base_url") or "").strip()
    api_key = str(body.get("api_key") or "").strip()
    if not name or not base_url or not api_key:
        raise HTTPException(status_code=400, detail="name, base_url, api_key are required")
    new_id = create_upstream(
        name=name,
        base_url=base_url,
        api_key=api_key,
        trust_env=bool(body.get("trust_env", False)),
        timeout_seconds=float(body.get("timeout_seconds") or 60.0),
        enabled=bool(body.get("enabled", True)),
        is_default=bool(body.get("is_default", False)),
    )
    await refresh_upstream_client(request.app)
    row = get_upstream(new_id)
    return JSONResponse(status_code=201, content=row)


@app.patch("/admin/upstreams/{upstream_id}")
async def admin_patch_upstream(request: Request, upstream_id: int) -> JSONResponse:
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    ok = update_upstream(
        upstream_id,
        name=body.get("name") if "name" in body else None,
        base_url=body.get("base_url") if "base_url" in body else None,
        api_key=body.get("api_key") if "api_key" in body else None,
        trust_env=body.get("trust_env") if "trust_env" in body else None,
        timeout_seconds=body.get("timeout_seconds")
        if "timeout_seconds" in body
        else None,
        enabled=body.get("enabled") if "enabled" in body else None,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="upstream not found")
    await refresh_upstream_client(request.app)
    row = get_upstream(upstream_id)
    return JSONResponse(content=row)


@app.delete("/admin/upstreams/{upstream_id}")
async def admin_delete_upstream(request: Request, upstream_id: int) -> JSONResponse:
    ok = delete_upstream(upstream_id)
    if not ok:
        raise HTTPException(status_code=404, detail="upstream not found")
    await refresh_upstream_client(request.app)
    return JSONResponse(content={"ok": True, "deleted_id": upstream_id})


@app.post("/admin/upstreams/{upstream_id}/set-default")
async def admin_set_default_upstream(request: Request, upstream_id: int) -> JSONResponse:
    ok = set_default_upstream(upstream_id)
    if not ok:
        raise HTTPException(status_code=404, detail="upstream not found or disabled")
    await refresh_upstream_client(request.app)
    row = get_upstream(upstream_id)
    return JSONResponse(content=row)


@app.get("/v1/models", dependencies=[Depends(verify_gateway_key)])
async def list_models(request: Request) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    start = time.perf_counter()
    client: UpstreamClient | None = getattr(request.app.state, "upstream_client", None)
    if client is None:
        return no_upstream_response()
    try:
        upstream_response = await client.list_models()
    except httpx.TimeoutException:
        return upstream_timeout_error()
    except httpx.HTTPError:
        return upstream_unavailable_error()

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    payload = parse_response_json(upstream_response)
    gw_path = "/v1/models"
    log_event(
        {
            "path": client.logged_upstream_url(gw_path),
            "model": None,
            "status_code": upstream_response.status_code,
            "latency_ms": elapsed_ms,
            "client_ip": client_ip,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "request_body": None,
            "response_body": payload,
            "session_id": DEFAULT_LOG_SESSION_ID,
        }
    )

    if upstream_response.is_error:
        return normalize_upstream_error(upstream_response.status_code, payload)
    return JSONResponse(status_code=upstream_response.status_code, content=payload)


@app.post(
    "/v1/chat/completions",
    dependencies=[Depends(verify_gateway_key)],
    response_model=None,
)
async def create_chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    client_ip = request.client.host if request.client else None
    client: UpstreamClient | None = getattr(request.app.state, "upstream_client", None)
    if client is None:
        return no_upstream_response()
    start = time.perf_counter()
    body = await read_request_json(request)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    session_id, upstream_body = _resolve_session_and_upstream_body(body)
    model = upstream_body.get("model")
    stream = bool(upstream_body.get("stream", False))

    try:
        if stream:
            upstream_response, stream_iter = await client.chat_completions_stream(
                upstream_body
            )
            if upstream_response.is_error:
                payload = parse_response_json(upstream_response)
                return normalize_upstream_error(upstream_response.status_code, payload)

            async def wrapped_stream() -> AsyncIterator[bytes]:
                # 流式响应时，response_body 记录的是完整拼接后的所有 chunk 内容。
                response_chunks: list[str] = []
                try:
                    async for chunk in stream_iter:
                        response_chunks.append(chunk.decode("utf-8", errors="ignore"))
                        yield chunk
                finally:
                    await upstream_response.aclose()
                    elapsed_ms = int((time.perf_counter() - start) * 1000)
                    gw_path = "/v1/chat/completions"
                    log_event(
                        {
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
                        }
                    )

            return StreamingResponse(
                wrapped_stream(),
                media_type=upstream_response.headers.get(
                    "content-type", "text/event-stream"
                ),
            )

        upstream_response = await client.chat_completions(upstream_body)
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
    log_event(
        {
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
        }
    )

    if upstream_response.is_error:
        return normalize_upstream_error(upstream_response.status_code, payload)
    return JSONResponse(status_code=upstream_response.status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return openai_error_response(
        message=str(exc.detail),
        status_code=exc.status_code,
        error_type="invalid_request_error",
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

