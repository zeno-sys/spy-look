"""解析全局大模型运行时配置，供其他工具调用。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from db.upstreams import get_upstream_runtime
from tools.gateway.services.upstream_client import (
    UpstreamRuntimeConfig,
    upstream_runtime_from_row,
)
from tools.settings.services.config_loader import load_config


@dataclass(slots=True)
class ResolvedLlmConfig:
    base_url: str
    api_key: str
    model: str
    extra_params: dict[str, Any]
    mode: str
    upstream_id: int | None = None
    timeout_seconds: float = 60.0
    trust_env: bool = False


async def resolve_llm_config(session: AsyncSession) -> ResolvedLlmConfig | None:
    """读取已保存的全局 LLM 配置并解析为可直连上游的运行时参数。

    未配置完整时返回 None。
    """
    llm = dict((load_config().get("llm") or {}))
    mode = str(llm.get("mode") or "custom")
    model = str(llm.get("model") or "").strip()
    if not model:
        return None

    extra = llm.get("extra_params") if isinstance(llm.get("extra_params"), dict) else {}

    if mode == "upstream":
        upstream_id = llm.get("upstream_id")
        if upstream_id is None:
            return None
        row = await get_upstream_runtime(session, int(upstream_id))
        if not row or not row.get("enabled"):
            return None
        cfg = upstream_runtime_from_row(row)
        if not cfg:
            return None
        return ResolvedLlmConfig(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            model=model,
            extra_params=dict(extra),
            mode="upstream",
            upstream_id=int(upstream_id),
            timeout_seconds=cfg.timeout_seconds,
            trust_env=cfg.trust_env,
        )

    base_url = str(llm.get("base_url") or "").strip()
    if not base_url:
        return None
    return ResolvedLlmConfig(
        base_url=base_url,
        api_key=str(llm.get("api_key") or "").strip(),
        model=model,
        extra_params=dict(extra),
        mode="custom",
        upstream_id=None,
        timeout_seconds=60.0,
        trust_env=False,
    )


def build_chat_payload(cfg: ResolvedLlmConfig, messages: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    """构造 chat/completions 请求体。

    extra_params 等价于 OpenAI SDK 的 extra_body：字段会合并进 HTTP 请求 JSON。
    """
    payload: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "stream": False,
    }
    for k, v in (cfg.extra_params or {}).items():
        if k in ("model", "messages"):
            continue
        payload[k] = v
    payload.update(overrides)
    payload["model"] = cfg.model
    payload["messages"] = messages
    return payload


def to_upstream_runtime(cfg: ResolvedLlmConfig) -> UpstreamRuntimeConfig:
    return UpstreamRuntimeConfig(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        timeout_seconds=cfg.timeout_seconds,
        trust_env=cfg.trust_env,
    )


def _extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("模型响应缺少 choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("模型响应 choices[0] 无效")
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        # 部分模型把内容放在 reasoning / 列表块里
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            joined = "".join(parts).strip()
            if joined:
                return joined
        # Qwen 思考模式：content 可能为空，尝试 reasoning_content
        for key in ("reasoning_content", "reasoning", "thinking"):
            alt = message.get(key)
            if isinstance(alt, str) and alt.strip():
                # 思考内容里可能夹带最终 JSON，尝试直接解析
                return alt.strip()
    text = first.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise ValueError("模型响应无可用文本内容")


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    # 容错：截取首尾花括号
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("期望 JSON 对象")
    return parsed


def _disable_thinking_flags(payload: dict[str, Any]) -> None:
    """生成测试文本时尽量关闭思考，保证稳定输出 JSON。"""
    payload["enable_thinking"] = False
    for key in list(payload.keys()):
        lower = key.lower()
        if key == "enable_thinking":
            continue
        if "thinking" in lower or lower in ("reasoning",):
            if isinstance(payload[key], bool):
                payload[key] = False
            elif isinstance(payload[key], dict):
                payload.pop(key, None)


async def chat_completion_json(
    session: AsyncSession,
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    """调用全局大模型并解析为 JSON 对象。"""
    import httpx

    from tools.gateway.services.upstream_client import upstream_auth_headers

    cfg = await resolve_llm_config(session)
    if cfg is None:
        raise ValueError("尚未配置全局大模型，请先到「设置 → 大模型」完成配置并保存")

    runtime = to_upstream_runtime(cfg)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    last_error: Exception | None = None
    for use_json_format in (True, False):
        payload = build_chat_payload(
            cfg,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        _disable_thinking_flags(payload)
        if use_json_format:
            payload["response_format"] = {"type": "json_object"}
        else:
            payload.pop("response_format", None)

        try:
            async with httpx.AsyncClient(
                base_url=runtime.base_url,
                timeout=max(runtime.timeout_seconds, 90.0),
                trust_env=runtime.trust_env,
            ) as client:
                resp = await client.post(
                    "/chat/completions",
                    headers=upstream_auth_headers(runtime.api_key),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            last_error = exc
            continue

        if resp.is_error:
            # response_format 不被支持时改试普通模式
            if use_json_format and resp.status_code in (400, 422):
                last_error = ValueError(f"HTTP {resp.status_code}: {(resp.text or '')[:300]}")
                continue
            detail = (resp.text or "")[:500]
            raise ValueError(f"全局大模型请求失败 HTTP {resp.status_code}: {detail}")

        try:
            data = resp.json()
        except ValueError as exc:
            last_error = exc
            continue
        if not isinstance(data, dict):
            last_error = ValueError("全局大模型返回格式无效")
            continue

        try:
            content = _extract_message_content(data)
            return _parse_json_object(content)
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise ValueError(f"无法解析模型返回的 JSON：{last_error}")


async def generate_probe_texts(
    session: AsyncSession,
    *,
    kind: str,
    document_count: int = 3,
) -> dict[str, Any]:
    """生成嵌入 / 重排序能力测试的占位文本。"""
    if kind == "embedding":
        system = (
            "你是测试数据生成助手。只输出一个 JSON 对象，不要 markdown，不要解释。"
            '格式严格为：{"text_a":"...","text_b":"..."}。'
            "text_a、text_b 均为简短中文（各不超过 40 字），主题相近但表述不同。"
        )
        user = "生成一对 embedding 相似度测试占位文本。"
        parsed = await chat_completion_json(session, system=system, user=user, max_tokens=400)
        text_a = str(parsed.get("text_a") or "").strip()
        text_b = str(parsed.get("text_b") or "").strip()
        if not text_a or not text_b:
            raise ValueError("模型未返回完整的 text_a / text_b")
        return {"kind": "embedding", "text_a": text_a, "text_b": text_b}

    if kind == "rerank":
        count = max(2, min(8, int(document_count or 3)))
        system = (
            "你是测试数据生成助手。只输出一个 JSON 对象，不要 markdown，不要解释。"
            f'格式严格为：{{"query":"...","documents":["...","..."]}}，documents 长度恰好 {count}。'
            "query 不超过 20 字；每条 document 不超过 30 字。"
            "相关度要有差异：含高度相关、部分相关、不太相关。"
        )
        user = f"生成 rerank 测试用的 query 与 {count} 条 documents。"
        parsed = await chat_completion_json(session, system=system, user=user, max_tokens=800)
        query = str(parsed.get("query") or "").strip()
        docs_raw = parsed.get("documents")
        if not query:
            raise ValueError("模型未返回 query")
        if not isinstance(docs_raw, list):
            raise ValueError("模型未返回 documents 数组")
        documents = [str(d).strip() for d in docs_raw if str(d).strip()]
        if len(documents) < 2:
            raise ValueError("documents 至少需要 2 条非空文本")
        if len(documents) > count:
            documents = documents[:count]
        return {"kind": "rerank", "query": query, "documents": documents}

    raise ValueError(f"不支持的 kind: {kind}")
