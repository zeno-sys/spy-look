"""
探测 OpenAI 兼容 API 的模型能力（纯 HTTP，不依赖 SDK）。

输入 uri、api_key、model，输出各项能力支持情况的 dict。

json_mode 探测等价于 SDK 的 completions.parse(response_format=PydanticModel)：
由 Pydantic 生成 json_schema 请求体，响应用 model_validate_json 校验。

vision 探测发送内嵌纯色 PNG（image_url data URL），要求模型识别主色，
以验证是否支持多模态图片理解。
"""

from __future__ import annotations

import base64
import json
import re
import struct
import zlib
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from tools.gateway.services.upstream_client import upstream_auth_headers

_THINKING_TAG = re.compile(
    r"(?:<think(?:ing)?>|</think(?:ing)?>|<think>|</think>)",
    re.IGNORECASE,
)

_WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, e.g. Beijing",
                },
            },
            "required": ["location"],
        },
    },
}


def _normalize_chat_url(uri: str) -> str:
    url = uri.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return f"{url}/chat/completions"


def _thinking_options(enable: bool) -> dict[str, Any]:
    return {
        "enable_thinking": enable,
        "chat_template_kwargs": {
            "enable_thinking": enable,
            "thinking": enable,
        },
        "thinking": {"type": "enabled" if enable else "disabled"},
    }


def _capability_result(
    *,
    supported: bool,
    detail: str | None = None,
    error: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {"supported": supported}
    if detail is not None:
        out["detail"] = detail
    if error is not None:
        out["error"] = error
    out.update(extra)
    return out


def _post_chat(
    client: httpx.Client,
    url: str,
    api_key: str,
    body: dict[str, Any],
) -> tuple[int, dict[str, Any] | None, str | None]:
    headers = upstream_auth_headers(api_key)
    try:
        resp = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        return 0, None, str(e)

    if resp.status_code != 200:
        return resp.status_code, None, resp.text

    try:
        return resp.status_code, resp.json(), None
    except json.JSONDecodeError as e:
        return resp.status_code, None, f"响应 JSON 解析失败: {e}; body={resp.text[:500]}"


def _first_message(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices") or []
    if not choices:
        return {}
    return choices[0].get("message") or {}


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _detect_thinking_in_message(message: dict[str, Any]) -> tuple[bool, str | None]:
    signals: list[str] = []

    for field in ("reasoning_content", "reasoning"):
        value = message.get(field)
        if isinstance(value, str) and value.strip():
            signals.append(field)

    content = message.get("content")
    if isinstance(content, str) and _THINKING_TAG.search(content):
        signals.append("thinking_tag_in_content")

    if signals:
        return True, ", ".join(signals)
    return False, None


def _test_chat_completion(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "max_tokens": max_tokens,
        "stream": False,
        **_thinking_options(False),
    }
    status, data, err = _post_chat(client, url, api_key, body)
    if err:
        return _capability_result(supported=False, error=err, status_code=status)

    message = _first_message(data)
    content = message.get("content")
    supported = isinstance(content, str) and bool(content.strip())
    return _capability_result(
        supported=supported,
        detail=(content or "")[:200] if supported else "响应无有效 content",
        status_code=status,
        finish_reason=(data.get("choices") or [{}])[0].get("finish_reason"),
    )


def _test_tool_calling(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "What's the weather in Beijing today?"}],
        "tools": [_WEATHER_TOOL],
        "tool_choice": "auto",
        "max_tokens": max_tokens,
        "stream": False,
        **_thinking_options(False),
    }
    status, data, err = _post_chat(client, url, api_key, body)
    if err:
        return _capability_result(supported=False, error=err, status_code=status)

    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    tool_calls = message.get("tool_calls") or []
    finish_reason = choice.get("finish_reason")

    if tool_calls:
        first = tool_calls[0]
        fn = first.get("function") or {}
        return _capability_result(
            supported=True,
            detail=f"tool_calls: {fn.get('name')}",
            finish_reason=finish_reason,
            status_code=status,
        )

    function_call = message.get("function_call")
    if function_call:
        return _capability_result(
            supported=True,
            detail=f"function_call: {function_call.get('name')}",
            finish_reason=finish_reason,
            status_code=status,
            legacy_format=True,
        )

    return _capability_result(
        supported=False,
        detail="请求成功但未返回 tool_calls / function_call",
        finish_reason=finish_reason,
        status_code=status,
        content_preview=(message.get("content") or "")[:200],
    )


class _UserInfo(BaseModel):
    name: str
    age: int
    city: str
    hobbies: list[str]


def _pydantic_response_format(model: type[BaseModel]) -> dict[str, Any]:
    schema = dict(model.model_json_schema())
    schema.setdefault("additionalProperties", False)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model.__name__,
            "strict": True,
            "schema": schema,
        },
    }


def _test_json_mode(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": "张三，28岁，北京，爱好游泳和读书"}
        ],
        "response_format": _pydantic_response_format(_UserInfo),
        "max_tokens": max_tokens,
        "stream": False,
        **_thinking_options(False),
    }
    status, data, err = _post_chat(client, url, api_key, body)
    if err:
        param_rejected = status == 400 and (
            "response_format" in err.lower() or "json_schema" in err.lower()
        )
        return _capability_result(
            supported=False,
            error=err,
            status_code=status,
            param_rejected=param_rejected,
            mode="pydantic_parse",
        )

    message = _first_message(data)
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return _capability_result(
            supported=False,
            detail="响应无 content",
            status_code=status,
            mode="pydantic_parse",
        )

    try:
        user = _UserInfo.model_validate_json(content)
    except ValidationError as e:
        return _capability_result(
            supported=False,
            detail=f"Pydantic 解析失败（等价于 message.parsed 不可用）: {e}",
            status_code=status,
            content_preview=content[:200],
            mode="pydantic_parse",
        )

    return _capability_result(
        supported=True,
        detail=(
            f"UserInfo 解析成功: name={user.name}, age={user.age}, "
            f"city={user.city}, hobbies={user.hobbies}"
        ),
        status_code=status,
        parsed=user.model_dump(),
        mode="pydantic_parse",
    )


_THINKING_PROBE_PROMPT = "17加25等于多少？请逐步思考后给出最终答案。"


def _thinking_probe_once(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
    *,
    enable_thinking: bool,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": _THINKING_PROBE_PROMPT}],
        "max_tokens": max_tokens,
        "stream": False,
        **_thinking_options(enable_thinking),
    }
    status, data, err = _post_chat(client, url, api_key, body)
    label = "开启" if enable_thinking else "关闭"

    if err:
        return _capability_result(
            supported=False,
            error=err,
            status_code=status,
            enable_thinking=enable_thinking,
            label=label,
        )

    message = _first_message(data)
    has_thinking, signal = _detect_thinking_in_message(message)
    content = message.get("content") or ""

    return _capability_result(
        supported=True,
        has_thinking=has_thinking,
        detail=signal if has_thinking else "未检测到思考内容",
        status_code=status,
        enable_thinking=enable_thinking,
        label=label,
        content_preview=str(content)[:200] if content else None,
    )


def _classify_thinking_mode(
    enabled_has: bool,
    disabled_has: bool,
    *,
    enabled_ok: bool,
    disabled_ok: bool,
) -> tuple[str, str, bool]:
    if not enabled_ok or not disabled_ok:
        return "unknown", "探测请求失败，无法判定思考模式", False

    if enabled_has and not disabled_has:
        return "hybrid", "混合模式：开启思考参数有思考内容，关闭后无思考，可控制", True
    if enabled_has and disabled_has:
        return "thinking_only", "思考模式：关闭思考参数后仍返回思考内容，无法通过参数关闭", True
    if not enabled_has and not disabled_has:
        return "not_supported", "不支持思考：开启/关闭思考参数均未检测到思考内容", False
    return "unknown", "异常：关闭时有思考、开启时无思考，行为不符合常见模式", False


_THINKING_MODE_LABELS: dict[str, str] = {
    "hybrid": "混合模式（可开可关）",
    "thinking_only": "思考模式（仅思考，无法关闭）",
    "not_supported": "不支持思考",
    "unknown": "未知/异常",
}


def _test_thinking(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    enabled = _thinking_probe_once(client, url, api_key, model, max_tokens, enable_thinking=True)
    disabled = _thinking_probe_once(client, url, api_key, model, max_tokens, enable_thinking=False)

    enabled_has = bool(enabled.get("has_thinking"))
    disabled_has = bool(disabled.get("has_thinking"))
    enabled_ok = enabled.get("supported") and enabled.get("error") is None
    disabled_ok = disabled.get("supported") and disabled.get("error") is None

    mode, detail, supported = _classify_thinking_mode(
        enabled_has, disabled_has, enabled_ok=enabled_ok, disabled_ok=disabled_ok
    )

    return _capability_result(
        supported=supported,
        detail=detail,
        mode=mode,
        mode_label=_THINKING_MODE_LABELS.get(mode, mode),
        enabled=enabled,
        disabled=disabled,
        summary={
            "开启思考参数": "有思考" if enabled_has else "无思考",
            "关闭思考参数": "有思考" if disabled_has else "无思考",
        },
    )


def _solid_color_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    raw = b"".join(b"\x00" + bytes([r, g, b]) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


_VISION_PROBE_RGB = (220, 20, 60)  # crimson red
_VISION_PROBE_PNG_B64 = base64.b64encode(_solid_color_png(64, 64, _VISION_PROBE_RGB)).decode("ascii")
_VISION_PROBE_DATA_URL = f"data:image/png;base64,{_VISION_PROBE_PNG_B64}"
_VISION_PROBE_PROMPT = (
    "What is the dominant color of this image? "
    "Reply with exactly one word in English: red, green, blue, yellow, or other."
)
_VISION_REJECT_HINTS = (
    "image",
    "vision",
    "multimodal",
    "multi-modal",
    "image_url",
    "does not support",
    "not support",
    "unsupported",
    "only text",
    "text-only",
    "无法处理",
    "不支持",
    "图片",
    "多模态",
)


def _content_mentions_red(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in ("red", "crimson", "scarlet")):
        return True
    return any(marker in text for marker in ("红色", "赤色", "红"))


def _looks_like_vision_rejection(status: int, err: str) -> bool:
    if status not in (400, 404, 415, 422):
        return False
    lowered = err.lower()
    return any(hint in lowered for hint in _VISION_REJECT_HINTS)


def _test_vision(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _VISION_PROBE_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": _VISION_PROBE_DATA_URL},
                    },
                ],
            }
        ],
        "max_tokens": max_tokens,
        "stream": False,
        **_thinking_options(False),
    }
    status, data, err = _post_chat(client, url, api_key, body)
    if err:
        return _capability_result(
            supported=False,
            error=err,
            status_code=status,
            param_rejected=_looks_like_vision_rejection(status, err),
            mode="image_url",
        )

    message = _first_message(data)
    content = _message_text(message).strip()
    finish_reason = (data.get("choices") or [{}])[0].get("finish_reason")
    if not content:
        return _capability_result(
            supported=False,
            detail="响应无有效 content",
            status_code=status,
            finish_reason=finish_reason,
            mode="image_url",
        )

    if _content_mentions_red(content):
        return _capability_result(
            supported=True,
            detail=f"模型识别出图片主色为红色: {content[:120]}",
            status_code=status,
            finish_reason=finish_reason,
            content_preview=content[:200],
            mode="image_url",
            expected_color="red",
        )

    return _capability_result(
        supported=False,
        detail="请求成功，但回复未正确识别出红色图片",
        status_code=status,
        finish_reason=finish_reason,
        content_preview=content[:200],
        mode="image_url",
        expected_color="red",
    )


def probe_model_capabilities(
    uri: str,
    api_key: str,
    model: str,
    *,
    timeout: float = 120.0,
    max_tokens: int = 256,
) -> dict[str, Any]:
    url = _normalize_chat_url(uri)
    result: dict[str, Any] = {
        "uri": uri,
        "endpoint": url,
        "model": model,
    }

    with httpx.Client(timeout=timeout) as client:
        chat = _test_chat_completion(client, url, api_key, model, max_tokens)
        result["chat_completion"] = chat

        if not chat["supported"]:
            skip = _capability_result(supported=False, detail="跳过：基础对话不可用")
            result["tool_calling"] = skip
            result["json_mode"] = skip
            result["thinking"] = skip
            result["vision"] = skip
            return result

        result["tool_calling"] = _test_tool_calling(client, url, api_key, model, max_tokens)
        result["json_mode"] = _test_json_mode(client, url, api_key, model, max_tokens)
        result["thinking"] = _test_thinking(client, url, api_key, model, max_tokens)
        result["vision"] = _test_vision(client, url, api_key, model, max_tokens)

    return result
