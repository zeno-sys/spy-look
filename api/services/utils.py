from __future__ import annotations

import json
import re
from typing import Any


def estimate_tokens(text: str, model_type: str = "default") -> dict:
    if not text:
        return {"total_tokens": 0, "breakdown": {}, "char_count": 0}

    coefficients = {
        "default": {"chinese": 0.6, "english": 0.3, "digit": 0.2, "punctuation": 0.3, "space": 0.1},
    }
    coef = coefficients.get(model_type, coefficients["default"])

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    digits = len(re.findall(r'\d', text))
    punctuation = len(re.findall(r'[^\w\s]', text))
    spaces = len(re.findall(r'\s', text))

    other_chars = len(text) - (chinese_chars + english_chars + digits + punctuation + spaces)

    chinese_tokens = chinese_chars * coef["chinese"]
    english_tokens = english_chars * coef["english"]
    digit_tokens = digits * coef["digit"]
    punctuation_tokens = punctuation * coef["punctuation"]
    space_tokens = spaces * coef["space"]
    other_tokens = other_chars * 0.5

    total_tokens = chinese_tokens + english_tokens + digit_tokens + punctuation_tokens + space_tokens + other_tokens

    return {
        "total_tokens": int(total_tokens),
        "char_count": len(text),
        "breakdown": {
            "chinese_chars": chinese_chars,
            "chinese_tokens": int(chinese_tokens),
            "english_chars": english_chars,
            "english_tokens": int(english_tokens),
            "digits": digits,
            "digit_tokens": int(digit_tokens),
            "punctuation": punctuation,
            "punctuation_tokens": int(punctuation_tokens),
            "spaces": spaces,
            "space_tokens": int(space_tokens),
            "other_chars": other_chars,
            "other_tokens": int(other_tokens)
        }
    }


def chat_messages_to_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(f"{role}: {content}")
        elif isinstance(content, list):
            text_parts = [
                str(item.get("text") or "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            if text_parts:
                parts.append(f"{role}: {' '.join(text_parts)}")
    return "\n".join(parts)


def stream_tokens_from_sse(
    sse_text: str, messages: list[dict[str, Any]] | None = None
) -> tuple[int | None, int | None, int | None]:
    if not sse_text:
        return None, None, None

    lines = sse_text.split("\n")
    usage: dict[str, Any] | None = None
    output_parts: list[str] = []

    for line in lines:
        if not line.startswith("data:"):
            continue
        candidate = line[5:].strip()
        if not candidate or candidate == "[DONE]":
            continue
        try:
            obj = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        if isinstance(obj.get("usage"), dict):
            usage = obj["usage"]
        for choice in obj.get("choices") or []:
            delta = choice.get("delta") if isinstance(choice, dict) else None
            if not isinstance(delta, dict):
                continue
            if isinstance(delta.get("content"), str):
                output_parts.append(delta["content"])
            if isinstance(delta.get("reasoning_content"), str):
                output_parts.append(delta["reasoning_content"])

    if usage:
        return (
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )

    input_tokens = None
    output_tokens = None
    if messages:
        text = chat_messages_to_text(messages)
        input_tokens = estimate_tokens(text)["total_tokens"] if text else None
    if output_parts:
        output_tokens = estimate_tokens("".join(output_parts))["total_tokens"]

    if input_tokens is not None or output_tokens is not None:
        total = (input_tokens or 0) + (output_tokens or 0)
    else:
        total = None
    return input_tokens, output_tokens, total
