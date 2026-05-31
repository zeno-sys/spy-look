from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class UpstreamRuntimeConfig:
    base_url: str
    api_key: str
    timeout_seconds: float = 60.0
    trust_env: bool = False


def upstream_request_url(base_url: str, gateway_path: str) -> str:
    """将网关路由（如 /v1/chat/completions）转为当前上游 base_url 下的实际请求 URL。"""
    base = str(base_url or "").strip().rstrip("/")
    gp = str(gateway_path or "").strip()
    if not base:
        return gp
    if gp.startswith("/v1/"):
        rest = gp[len("/v1/"):].lstrip("/")
        return f"{base}/{rest}" if rest else base
    if gp == "/v1":
        return base
    if gp.startswith("/"):
        return f"{base}{gp}"
    return f"{base}/{gp}"


def upstream_runtime_from_row(row: dict[str, Any]) -> UpstreamRuntimeConfig | None:
    if not row:
        return None
    base = str(row.get("base_url") or "").strip()
    key = str(row.get("api_key") or "")
    if not base or not key:
        return None
    return UpstreamRuntimeConfig(
        base_url=base,
        api_key=key,
        timeout_seconds=float(row.get("timeout_seconds") or 60.0),
        trust_env=bool(row.get("trust_env")),
    )


class UpstreamClient:
    def __init__(self, cfg: UpstreamRuntimeConfig):
        self._cfg = cfg
        self._client = httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            trust_env=cfg.trust_env,
        )

    def logged_upstream_url(self, gateway_path: str) -> str:
        return upstream_request_url(self._cfg.base_url, gateway_path)

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }

    async def list_models(self) -> httpx.Response:
        return await self._client.get("/models", headers=self._headers())

    async def chat_completions(self, payload: dict[str, Any]) -> httpx.Response:
        return await self._client.post(
            "/chat/completions",
            headers=self._headers(),
            json=payload,
        )

    async def chat_completions_stream(
        self, payload: dict[str, Any]
    ) -> tuple[httpx.Response, AsyncIterator[bytes]]:
        request = self._client.build_request(
            "POST",
            "/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        response = await self._client.send(request, stream=True)
        return response, response.aiter_bytes()
