"""
测量 OpenAI 兼容 API 的中文文本生成速度（tokens/s）。

流程：预热 1 次 → 串行正式测试 3 次 → 取平均。
使用流式请求，以首 token 到流结束的时间段计算生成速度。
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from tools.gateway.services.capability_probe import _normalize_chat_url
from tools.gateway.services.utils import estimate_tokens

_CHINESE_TEST_PROMPT = (
    "请用中文写一段关于人工智能如何改变日常生活的短文，"
    "内容涵盖工作、学习和娱乐等方面，字数约 200 字，语言流畅自然。"
)

_BENCHMARK_RUNS = 3

ProgressCallback = Callable[[str, str, int, dict[str, Any] | None], None]


def _post_stream_speed(
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": _CHINESE_TEST_PROMPT}],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    t_start = time.perf_counter()
    t_first_token: float | None = None
    completion_tokens: int | None = None
    output_parts: list[str] = []
    status_code = 0
    error: str | None = None

    try:
        with client.stream("POST", url, headers=headers, json=body) as resp:
            status_code = resp.status_code
            if resp.is_error:
                error = resp.read().decode("utf-8", errors="replace")[:800]
                return _result_from_error(status_code, error, t_start)

            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if not isinstance(chunk, dict):
                    continue

                usage = chunk.get("usage")
                if isinstance(usage, dict) and usage.get("completion_tokens") is not None:
                    completion_tokens = int(usage["completion_tokens"])

                for choice in chunk.get("choices") or []:
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta") or {}
                    if not isinstance(delta, dict):
                        continue
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        if t_first_token is None:
                            t_first_token = time.perf_counter()
                        output_parts.append(content)
                    reasoning = delta.get("reasoning_content")
                    if isinstance(reasoning, str) and reasoning:
                        if t_first_token is None:
                            t_first_token = time.perf_counter()
                        output_parts.append(reasoning)
    except httpx.HTTPError as exc:
        return _result_from_error(0, str(exc), t_start)

    t_end = time.perf_counter()
    if completion_tokens is None and output_parts:
        completion_tokens = estimate_tokens("".join(output_parts))["total_tokens"]

    if completion_tokens is None or completion_tokens <= 0:
        return {
            "ok": False,
            "error": error or "未获取到有效输出 token 数",
            "status_code": status_code,
            "elapsed_ms": int((t_end - t_start) * 1000),
        }

    total_ms = (t_end - t_start) * 1000
    ttft_ms = int((t_first_token - t_start) * 1000) if t_first_token else None
    gen_seconds = (t_end - t_first_token) if t_first_token else (t_end - t_start)
    tokens_per_sec = round(completion_tokens / gen_seconds, 2) if gen_seconds > 0 else 0.0

    return {
        "ok": True,
        "status_code": status_code,
        "completion_tokens": completion_tokens,
        "elapsed_ms": int(total_ms),
        "ttft_ms": ttft_ms,
        "generation_ms": int(gen_seconds * 1000),
        "tokens_per_sec": tokens_per_sec,
        "content_preview": "".join(output_parts)[:200] if output_parts else None,
    }


def _result_from_error(status_code: int, error: str, t_start: float) -> dict[str, Any]:
    return {
        "ok": False,
        "status_code": status_code,
        "error": error,
        "elapsed_ms": int((time.perf_counter() - t_start) * 1000),
    }


def _average_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    ok_runs = [r for r in runs if r.get("ok")]
    if not ok_runs:
        return {"ok": False, "error": "所有测试轮次均失败"}

    n = len(ok_runs)
    return {
        "ok": True,
        "runs_count": n,
        "completion_tokens": round(sum(r["completion_tokens"] for r in ok_runs) / n, 1),
        "elapsed_ms": round(sum(r["elapsed_ms"] for r in ok_runs) / n),
        "ttft_ms": round(sum(r.get("ttft_ms") or 0 for r in ok_runs) / n),
        "generation_ms": round(sum(r.get("generation_ms") or 0 for r in ok_runs) / n),
        "tokens_per_sec": round(sum(r["tokens_per_sec"] for r in ok_runs) / n, 2),
    }


def test_token_speed(
    uri: str,
    api_key: str,
    model: str,
    *,
    timeout: float = 120.0,
    max_tokens: int = 256,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    def _progress(stage: str, message: str, percent: int, extra: dict[str, Any] | None = None) -> None:
        if on_progress is not None:
            on_progress(stage, message, percent, extra)

    url = _normalize_chat_url(uri)
    result: dict[str, Any] = {
        "uri": uri,
        "endpoint": url,
        "model": model,
        "prompt": _CHINESE_TEST_PROMPT,
        "max_tokens": max_tokens,
        "benchmark_runs": _BENCHMARK_RUNS,
    }

    with httpx.Client(timeout=timeout) as client:
        _progress("warmup", "正在预热（第 0 轮，不计入统计）...", 0)
        warmup = _post_stream_speed(client, url, api_key, model, max_tokens)
        result["warmup"] = warmup
        if warmup.get("ok"):
            _progress(
                "warmup",
                f"预热完成 · {warmup.get('tokens_per_sec', '-')} tokens/s",
                25,
                {"result": warmup},
            )
        else:
            _progress("warmup", f"预热失败: {warmup.get('error', '未知错误')}", 25, {"result": warmup})

        if not warmup.get("ok"):
            result["runs"] = []
            result["average"] = {"ok": False, "error": f"预热失败: {warmup.get('error')}"}
            return result

        runs: list[dict[str, Any]] = []
        for i in range(_BENCHMARK_RUNS):
            run_num = i + 1
            start_percent = 25 + i * 25
            _progress(
                "run",
                f"正在进行第 {run_num}/{_BENCHMARK_RUNS} 轮测试...",
                start_percent,
                {"run": run_num},
            )
            run = _post_stream_speed(client, url, api_key, model, max_tokens)
            run["run"] = run_num
            runs.append(run)
            end_percent = 25 + run_num * 25
            if run.get("ok"):
                _progress(
                    "run",
                    f"第 {run_num} 轮完成 · {run.get('tokens_per_sec', '-')} tokens/s",
                    end_percent,
                    {"run": run_num, "result": run},
                )
            else:
                _progress(
                    "run",
                    f"第 {run_num} 轮失败: {run.get('error', '未知错误')}",
                    end_percent,
                    {"run": run_num, "result": run},
                )

    result["runs"] = runs
    result["average"] = _average_runs(runs)
    _progress("complete", "测速完成，正在生成报告...", 100)
    return result
