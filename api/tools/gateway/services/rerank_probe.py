"""
探测 OpenAI / Jina / Cohere 兼容 rerank API：对 query + documents 返回重排序结果。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from tools.gateway.services.upstream_client import upstream_auth_headers


def _normalize_rerank_url(uri: str) -> str:
    url = uri.rstrip("/")
    if url.endswith("/rerank"):
        return url
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return f"{url}/rerank"


def _result_score(item: dict[str, Any]) -> float | None:
    for key in ("relevance_score", "score", "relevanceScore"):
        value = item.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _result_document_text(item: dict[str, Any], documents: list[str], index: int) -> str:
    doc = item.get("document")
    if isinstance(doc, str) and doc.strip():
        return doc
    if isinstance(doc, dict):
        for key in ("text", "content", "document"):
            value = doc.get(key)
            if isinstance(value, str) and value.strip():
                return value
    if 0 <= index < len(documents):
        return documents[index]
    return ""


def _normalize_results(data: dict[str, Any], documents: list[str]) -> list[dict[str, Any]]:
    raw = data.get("results")
    if not isinstance(raw, list) or not raw:
        raise ValueError("响应缺少 results 数组")

    normalized: list[dict[str, Any]] = []
    for rank, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError("results 项格式无效")
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"results 项缺少有效 index: {exc}") from exc
        score = _result_score(item)
        if score is None:
            raise ValueError(f"results[{index}] 缺少 relevance_score / score")
        normalized.append(
            {
                "rank": rank,
                "index": index,
                "relevance_score": round(score, 6),
                "document": _result_document_text(item, documents, index),
            }
        )

    # 部分上游未必按分数排序，统一按分数降序再重新编号
    normalized.sort(key=lambda row: row["relevance_score"], reverse=True)
    for rank, row in enumerate(normalized, start=1):
        row["rank"] = rank
    return normalized


def probe_rerank(
    uri: str,
    api_key: str,
    model: str,
    query: str,
    documents: list[str],
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    url = _normalize_rerank_url(uri)
    body = {
        "model": model,
        "query": query,
        "documents": documents,
    }
    headers = upstream_auth_headers(api_key)

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "query": query,
            "supported": False,
            "status_code": 0,
            "error": str(exc),
            "detail": "请求 rerank 接口失败",
        }

    if resp.status_code != 200:
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "query": query,
            "supported": False,
            "status_code": resp.status_code,
            "error": resp.text,
            "detail": f"rerank 接口返回 HTTP {resp.status_code}",
        }

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "query": query,
            "supported": False,
            "status_code": resp.status_code,
            "error": f"响应 JSON 解析失败: {exc}; body={resp.text[:500]}",
            "detail": "无法解析 rerank 响应",
        }

    if not isinstance(data, dict):
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "query": query,
            "supported": False,
            "status_code": resp.status_code,
            "error": "响应不是 JSON 对象",
            "detail": "无法解析 rerank 响应",
        }

    try:
        results = _normalize_results(data, documents)
    except ValueError as exc:
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "query": query,
            "supported": False,
            "status_code": resp.status_code,
            "error": str(exc),
            "detail": "无法从响应解析排序结果",
        }

    return {
        "uri": uri,
        "endpoint": url,
        "model": model,
        "query": query,
        "supported": True,
        "status_code": resp.status_code,
        "document_count": len(documents),
        "results": results,
        "detail": f"成功对 {len(documents)} 条结果完成重排序",
        "error": None,
    }
