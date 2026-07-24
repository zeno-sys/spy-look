from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.engine import get_session
from db.upstreams import get_upstream, get_upstream_runtime, list_enabled_upstream_rows, mask_api_key
from tools.gateway.services.upstream_client import (
    UpstreamRuntimeConfig,
    upstream_auth_headers,
    upstream_runtime_from_row,
)
from tools.settings.schemas import (
    AppSettings,
    AppSettingsPatch,
    GenerateProbeTextsRequest,
    LlmConnectivityTestRequest,
    LlmSettings,
)
from tools.settings.services.config_loader import load_config, reload_config, save_config
from tools.settings.services.llm import generate_probe_texts

router = APIRouter(prefix="/settings/admin", tags=["settings-admin"])


def _mask_llm(llm: dict[str, Any]) -> dict[str, Any]:
    out = dict(llm)
    if out.get("api_key"):
        out["api_key"] = mask_api_key(str(out["api_key"]))
    else:
        out["api_key"] = ""
    return out


def _mask_config(data: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(data)
    cfg["llm"] = _mask_llm(dict(cfg.get("llm") or {}))
    return cfg


def _merge_llm(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in patch.items():
        if value is None:
            continue
        if key == "api_key" and isinstance(value, str) and not value.strip():
            continue
        merged[key] = value
    return merged


def _upstream_option_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": str(row.get("name") or ""),
        "base_url": str(row.get("base_url") or ""),
        "api_key_masked": mask_api_key(str(row.get("api_key") or "")),
        "enabled": bool(row.get("enabled", True)),
    }


async def _resolve_runtime(
    session: AsyncSession,
    *,
    mode: str,
    upstream_id: int | None,
    base_url: str,
    api_key: str,
) -> UpstreamRuntimeConfig:
    if mode == "upstream":
        if upstream_id is None or int(upstream_id) < 1:
            raise HTTPException(status_code=400, detail="请选择网关模型源")
        row = await get_upstream_runtime(session, int(upstream_id))
        if not row:
            raise HTTPException(status_code=400, detail="模型源不存在")
        if not row.get("enabled"):
            raise HTTPException(status_code=400, detail="模型源已禁用")
        cfg = upstream_runtime_from_row(row)
        if not cfg:
            raise HTTPException(status_code=400, detail="模型源 base_url 无效")
        return cfg

    url = str(base_url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="base_url 不能为空")
    return UpstreamRuntimeConfig(
        base_url=url,
        api_key=str(api_key or "").strip(),
        timeout_seconds=60.0,
        trust_env=False,
    )


@router.get("/config")
async def get_config(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    data = _mask_config(load_config())
    llm = dict(data.get("llm") or {})
    # 上游模式时附带模型源展示信息
    if llm.get("mode") == "upstream" and llm.get("upstream_id"):
        row = await get_upstream(session, int(llm["upstream_id"]))
        if row:
            llm["upstream_name"] = row.get("name")
            llm["upstream_base_url"] = row.get("base_url")
            llm["upstream_api_key_masked"] = row.get("api_key_masked")
    data["llm"] = llm
    return data


@router.api_route("/config", methods=["PATCH", "POST"])
async def patch_config(body: AppSettingsPatch) -> dict[str, Any]:
    current = load_config()
    patch = body.model_dump(exclude_none=True)
    if body.llm is not None:
        llm_patch = body.llm.model_dump(exclude_none=True)
        if "api_key" in llm_patch and not str(llm_patch.get("api_key") or "").strip():
            llm_patch.pop("api_key", None)
        # 切到上游模式时清空本地凭证，避免残留
        mode = llm_patch.get("mode", (current.get("llm") or {}).get("mode"))
        if mode == "upstream":
            llm_patch.setdefault("base_url", "")
            # 显式清空本地 key（空字符串在 merge 中会被跳过，这里直接写）
            merged_llm = _merge_llm(dict(current.get("llm") or {}), llm_patch)
            merged_llm["api_key"] = ""
            merged_llm["base_url"] = ""
        else:
            merged_llm = _merge_llm(dict(current.get("llm") or {}), llm_patch)
            merged_llm["upstream_id"] = None
        patch["llm"] = merged_llm
    merged = {**current, **patch}
    try:
        validated = AppSettings.model_validate(merged)
        LlmSettings.model_validate(merged.get("llm") or {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}") from exc

    mode = validated.llm.mode
    llm = validated.llm
    if mode == "upstream" and not llm.upstream_id:
        raise HTTPException(status_code=400, detail="请选择网关模型源")
    if mode == "custom" and not str(llm.base_url or "").strip():
        raise HTTPException(status_code=400, detail="base_url 不能为空")
    if not str(llm.model or "").strip():
        raise HTTPException(status_code=400, detail="model 不能为空")

    to_save = validated.model_dump()
    save_config(to_save)
    reload_config()
    return _mask_config(to_save)


@router.get("/llm/upstream-options")
async def llm_upstream_options(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    rows = await list_enabled_upstream_rows(session)
    return JSONResponse(content={"upstreams": [_upstream_option_public(row) for row in rows]})


@router.post("/llm/test")
async def llm_connectivity_test(
    body: LlmConnectivityTestRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    saved = dict((load_config().get("llm") or {}))
    api_key = str(body.api_key or "").strip()
    if body.mode == "custom" and (body.use_saved_api_key or not api_key):
        api_key = str(saved.get("api_key") or "")

    model = str(body.model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model 不能为空")

    cfg = await _resolve_runtime(
        session,
        mode=body.mode,
        upstream_id=body.upstream_id,
        base_url=body.base_url,
        api_key=api_key,
    )

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    extra = body.extra_params if isinstance(body.extra_params, dict) else {}
    # extra_params 合并进请求体（除 model/messages 外允许覆盖）
    for k, v in extra.items():
        if k in ("model", "messages"):
            continue
        payload[k] = v

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            trust_env=cfg.trust_env,
        ) as client:
            resp = await client.post(
                "/chat/completions",
                headers=upstream_auth_headers(cfg.api_key),
                json=payload,
            )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": "timeout",
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "request_url": f"{cfg.base_url.rstrip('/')}/chat/completions",
                "request_body": payload,
            },
        )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": str(exc),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "request_url": f"{cfg.base_url.rstrip('/')}/chat/completions",
                "request_body": payload,
            },
        )

    latency_ms = int((time.perf_counter() - t0) * 1000)
    try:
        preview: Any = resp.json()
    except ValueError:
        preview = {"raw": (resp.text or "")[:800]}

    return JSONResponse(
        status_code=200,
        content={
            "ok": not resp.is_error,
            "upstream_status_code": resp.status_code,
            "latency_ms": latency_ms,
            "request_url": f"{cfg.base_url.rstrip('/')}/chat/completions",
            "request_body": payload,
            "body": preview,
        },
    )


@router.post("/llm/generate-probe-texts")
async def llm_generate_probe_texts(
    body: GenerateProbeTextsRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        result = await generate_probe_texts(
            session,
            kind=body.kind,
            document_count=body.document_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成占位文本失败：{exc}") from exc
    return JSONResponse(content=result)
