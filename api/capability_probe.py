"""
探测 OpenAI 兼容 API 的模型能力（纯 HTTP，不依赖 SDK）。

输入 uri、api_key、model，输出各项能力支持情况的 dict。

json_mode 探测等价于 SDK 的 completions.parse(response_format=PydanticModel)：
由 Pydantic 生成 json_schema 请求体，响应用 model_validate_json 校验。
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

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
    """将 base URL 规范化为 chat/completions 完整地址。"""
    url = uri.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return f"{url}/chat/completions"


def _thinking_options(enable: bool) -> dict[str, Any]:
    """兼容常见后端的 thinking 参数字段。"""
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
    """发起 chat/completions 请求，返回 (status_code, json_body, error_text)。"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
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


def _detect_thinking_in_message(message: dict[str, Any]) -> tuple[bool, str | None]:
    """从单条 message 中检测是否包含思考内容。"""
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
        return _capability_result(
            supported=False,
            error=err,
            status_code=status,
        )

    message = _first_message(data)  # type: ignore[arg-type]
    content = message.get("content")
    supported = isinstance(content, str) and bool(content.strip())
    return _capability_result(
        supported=supported,
        detail=(content or "")[:200] if supported else "响应无有效 content",
        status_code=status,
        finish_reason=(data.get("choices") or [{}])[0].get("finish_reason"),  # type: ignore[union-attr]
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
        return _capability_result(
            supported=False,
            error=err,
            status_code=status,
        )

    choice = (data.get("choices") or [{}])[0]  # type: ignore[union-attr]
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

    # 部分后端用 function_call（旧格式）
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
    """与 OpenAI SDK completions.parse(response_format=UserInfo) 探测用例一致。"""

    name: str
    age: int
    city: str
    hobbies: list[str]


def _pydantic_response_format(model: type[BaseModel]) -> dict[str, Any]:
    """
    将 Pydantic 模型转为 HTTP 请求的 response_format。

    等价于 SDK：client.beta.chat.completions.parse(..., response_format=Model)
    """
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
            {
                "role": "user",
                "content": "张三，28岁，北京，爱好游泳和读书",
            }
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

    message = _first_message(data)  # type: ignore[arg-type]
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

_THINKING_MODE_LABELS: dict[str, str] = {
    "hybrid": "混合模式（可开可关）",
    "thinking_only": "思考模式（仅思考，无法关闭）",
    "not_supported": "不支持思考",
    "unknown": "未知/异常",
}


def _thinking_probe_once(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
    *,
    enable_thinking: bool,
) -> dict[str, Any]:
    """单次思考探测：指定 enable_thinking 后检查响应是否含思考内容。"""
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

    message = _first_message(data)  # type: ignore[arg-type]
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
    """
    根据开/关两次探测结果判定思考能力类型。

    - hybrid: 开启有思考、关闭无思考 → 混合模式，可控制
    - thinking_only: 关闭参数后仍有思考 → 思考模式，关不掉
    - not_supported: 开启也无思考 → 不支持
    """
    if not enabled_ok or not disabled_ok:
        return "unknown", "探测请求失败，无法判定思考模式", False

    if enabled_has and not disabled_has:
        return (
            "hybrid",
            "混合模式：开启思考参数有思考内容，关闭后无思考，可控制",
            True,
        )
    if enabled_has and disabled_has:
        return (
            "thinking_only",
            "思考模式：关闭思考参数后仍返回思考内容，无法通过参数关闭",
            True,
        )
    if not enabled_has and not disabled_has:
        return (
            "not_supported",
            "不支持思考：开启/关闭思考参数均未检测到思考内容",
            False,
        )
    return (
        "unknown",
        "异常：关闭时有思考、开启时无思考，行为不符合常见模式",
        False,
    )


def _test_thinking(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    enabled = _thinking_probe_once(
        client, url, api_key, model, max_tokens, enable_thinking=True
    )
    disabled = _thinking_probe_once(
        client, url, api_key, model, max_tokens, enable_thinking=False
    )

    enabled_has = bool(enabled.get("has_thinking"))
    disabled_has = bool(disabled.get("has_thinking"))
    enabled_ok = enabled.get("supported") and enabled.get("error") is None
    disabled_ok = disabled.get("supported") and disabled.get("error") is None

    mode, detail, supported = _classify_thinking_mode(
        enabled_has,
        disabled_has,
        enabled_ok=enabled_ok,
        disabled_ok=disabled_ok,
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


_CAPABILITY_LABELS: dict[str, tuple[str, str]] = {
    "chat_completion": ("基础对话", "能否正常完成 Chat Completions 请求并返回文本"),
    "tool_calling": ("工具调用", "是否支持 tools / tool_calls（Function Calling）"),
    "json_mode": ("结构化输出", "是否支持 Pydantic parse 等价能力（json_schema + 严格解析）"),
    "thinking": ("思考模式", "开/关 thinking 参数后是否可控制思考内容的输出"),
}

# ANSI 终端颜色（Windows 10+ / 现代终端均支持）
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_BLUE = "\033[34m"
_MAGENTA = "\033[35m"
_WHITE = "\033[97m"


def _ensure_utf8_stdout() -> None:
    """尽量让 Windows 终端正确显示中文与符号。"""
    stdout = sys.stdout
    if hasattr(stdout, "reconfigure"):
        try:
            stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _status_badge(supported: bool, *, skipped: bool = False) -> str:
    if skipped:
        return f"{_YELLOW}[已跳过]{_RESET}"
    if supported:
        return f"{_GREEN}[支持]{_RESET}"
    return f"{_RED}[不支持]{_RESET}"


def _kv(label: str, value: str, *, label_color: str = _CYAN) -> None:
    print(f"  {label_color}{label}{_RESET}: {value}")


def print_capability_report(report: dict[str, Any]) -> None:
    """
    以带颜色的中文格式打印 probe_model_capabilities 返回的结果 dict(为了自己测试好看结果用的)。
    """
    _ensure_utf8_stdout()

    width = 56
    line = "=" * width

    print(f"\n{_BOLD}{_MAGENTA}{line}{_RESET}")
    print(f"{_BOLD}{_MAGENTA}  模型能力探测报告{_RESET}")
    print(f"{_BOLD}{_MAGENTA}{line}{_RESET}\n")

    _kv("服务地址", report.get("uri", "-"), label_color=_BLUE)
    _kv("请求端点", report.get("endpoint", "-"), label_color=_BLUE)
    _kv("模型名称", report.get("model", "-"), label_color=_BLUE)

    if "total_elapsed_ms" in report:
        _kv("总耗时", f"{report['total_elapsed_ms']} ms", label_color=_BLUE)

    print(f"\n{_DIM}{'-' * width}{_RESET}")

    capability_keys = ("chat_completion", "tool_calling", "json_mode", "thinking")
    supported_count = 0
    tested_count = 0

    for key in capability_keys:
        item = report.get(key)
        if not isinstance(item, dict):
            continue

        title, desc = _CAPABILITY_LABELS.get(key, (key, ""))
        skipped = "跳过" in (item.get("detail") or "")
        supported = bool(item.get("supported"))

        if not skipped:
            tested_count += 1
            if supported:
                supported_count += 1

        print(f"\n{_BOLD}{_WHITE}【{title}】{_RESET} {_status_badge(supported, skipped=skipped)}")
        print(f"  {_DIM}{desc}{_RESET}")

        if item.get("detail"):
            _kv("说明", str(item["detail"]))

        if item.get("error"):
            print(f"  {_RED}错误{_RESET}: {item['error'][:500]}")

        if item.get("status_code") is not None:
            code = item["status_code"]
            code_color = _GREEN if code == 200 else _RED
            print(f"  {_CYAN}HTTP 状态{_RESET}: {code_color}{code}{_RESET}")

        if item.get("elapsed_ms") is not None:
            _kv("耗时", f"{item['elapsed_ms']} ms")

        if item.get("finish_reason"):
            _kv("结束原因", str(item["finish_reason"]))

        if item.get("parsed") is not None:
            parsed_text = json.dumps(item["parsed"], ensure_ascii=False, indent=2)
            print(f"  {_CYAN}解析结果{_RESET}:\n{_DIM}{parsed_text}{_RESET}")

        if item.get("content_preview"):
            _kv("内容预览", str(item["content_preview"]))

        if item.get("legacy_format"):
            print(f"  {_YELLOW}备注{_RESET}: 使用旧版 function_call 格式")

        if item.get("param_rejected"):
            print(f"  {_YELLOW}备注{_RESET}: 服务端可能拒绝了 response_format / json_schema 参数")

        if key == "thinking":
            if item.get("mode_label"):
                _kv("模式判定", str(item["mode_label"]), label_color=_MAGENTA)
            summary = item.get("summary")
            if isinstance(summary, dict):
                for k, v in summary.items():
                    _kv(k, str(v))
            for sub_key, sub_label in (("enabled", "开启思考参数"), ("disabled", "关闭思考参数")):
                sub = item.get(sub_key)
                if not isinstance(sub, dict):
                    continue
                has_th = sub.get("has_thinking")
                if has_th is True:
                    sub_status = f"{_GREEN}有思考{_RESET}"
                elif has_th is False:
                    sub_status = f"{_DIM}无思考{_RESET}"
                else:
                    sub_status = f"{_RED}请求失败{_RESET}"
                print(f"  {_CYAN}{sub_label}{_RESET}: {sub_status}", end="")
                if sub.get("detail") and sub.get("has_thinking"):
                    print(f"（{sub['detail']}）", end="")
                if sub.get("error"):
                    print(f" — {_RED}{str(sub['error'])[:120]}{_RESET}", end="")
                print()

    print(f"\n{_DIM}{'-' * width}{_RESET}")

    if tested_count == 0:
        summary = f"{_RED}未能完成任何有效探测{_RESET}"
    elif supported_count == tested_count:
        summary = f"{_GREEN}全部通过（{supported_count}/{tested_count}）{_RESET}"
    else:
        summary = f"{_YELLOW}部分通过（{supported_count}/{tested_count}）{_RESET}"

    print(f"\n{_BOLD}汇总{_RESET}: {summary}\n")


def probe_model_capabilities(
    uri: str,
    api_key: str,
    model: str,
    *,
    timeout: float = 120.0,
    max_tokens: int = 256,
) -> dict[str, Any]:
    """
    探测 OpenAI 兼容模型的各项能力。

    Args:
        uri: API 地址，如 http://host:8080/v1 或完整 .../v1/chat/completions
        api_key: Bearer token
        model: 模型名称
        timeout: 单次 HTTP 超时（秒）
        max_tokens: 各探测请求的最大生成长度

    Returns:
        包含各项能力支持情况的 dict
    """
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
            result["tool_calling"] = _capability_result(
                supported=False,
                detail="跳过：基础对话不可用",
            )
            result["json_mode"] = _capability_result(
                supported=False,
                detail="跳过：基础对话不可用",
            )
            result["thinking"] = _capability_result(
                supported=False,
                detail="跳过：基础对话不可用",
            )
            return result

        result["tool_calling"] = _test_tool_calling(client, url, api_key, model, max_tokens)
        result["json_mode"] = _test_json_mode(client, url, api_key, model, max_tokens)
        result["thinking"] = _test_thinking(client, url, api_key, model, max_tokens)

    return result



def main() -> None:
    import os

    uri = (os.environ.get("PROBE_URI") or "").strip()
    api_key = (os.environ.get("PROBE_API_KEY") or "").strip()
    model = (os.environ.get("PROBE_MODEL") or "").strip()
    if not uri or not api_key or not model:
        print(
            "用法: 设置环境变量 PROBE_URI、PROBE_API_KEY、PROBE_MODEL 后运行",
            file=sys.stderr,
        )
        raise SystemExit(1)
    report = probe_model_capabilities(uri, api_key, model)
    print_capability_report(report)


if __name__ == "__main__":
    main()
