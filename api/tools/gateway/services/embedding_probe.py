"""
探测 OpenAI 兼容 embeddings API：对两段文本取向量并计算余弦相似度。
"""

from __future__ import annotations

import json
import math
from typing import Any

import httpx

from tools.gateway.services.upstream_client import upstream_auth_headers


def _normalize_embeddings_url(uri: str) -> str:
    url = uri.rstrip("/")
    if url.endswith("/embeddings"):
        return url
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return f"{url}/embeddings"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"embedding dimensions mismatch: {len(a)} vs {len(b)}")
    if not a:
        raise ValueError("empty embedding vectors")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        raise ValueError("zero-norm embedding vector")
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _extract_embeddings(data: dict[str, Any]) -> list[list[float]]:
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise ValueError("响应缺少 data 数组")
    # OpenAI 兼容接口通常带 index，按 index 排序更稳妥
    sorted_items = sorted(
        items,
        key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0,
    )
    vectors: list[list[float]] = []
    for item in sorted_items:
        if not isinstance(item, dict):
            raise ValueError("data 项格式无效")
        emb = item.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise ValueError("响应缺少 embedding 向量")
        try:
            vectors.append([float(v) for v in emb])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"embedding 向量含非法数值: {exc}") from exc
    return vectors


def probe_embedding_similarity(
    uri: str,
    api_key: str,
    model: str,
    text_a: str,
    text_b: str,
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    url = _normalize_embeddings_url(uri)
    body = {
        "model": model,
        "input": [text_a, text_b],
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
            "supported": False,
            "status_code": 0,
            "error": str(exc),
            "detail": "请求 embeddings 接口失败",
        }

    if resp.status_code != 200:
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "supported": False,
            "status_code": resp.status_code,
            "error": resp.text,
            "detail": f"embeddings 接口返回 HTTP {resp.status_code}",
        }

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "supported": False,
            "status_code": resp.status_code,
            "error": f"响应 JSON 解析失败: {exc}; body={resp.text[:500]}",
            "detail": "无法解析 embeddings 响应",
        }

    if not isinstance(data, dict):
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "supported": False,
            "status_code": resp.status_code,
            "error": "响应不是 JSON 对象",
            "detail": "无法解析 embeddings 响应",
        }

    try:
        vectors = _extract_embeddings(data)
        if len(vectors) < 2:
            raise ValueError(f"期望至少 2 个 embedding，实际 {len(vectors)} 个")
        vec_a, vec_b = vectors[0], vectors[1]
        similarity = _cosine_similarity(vec_a, vec_b)
    except ValueError as exc:
        return {
            "uri": uri,
            "endpoint": url,
            "model": model,
            "supported": False,
            "status_code": resp.status_code,
            "error": str(exc),
            "detail": "无法从响应计算余弦相似度",
        }

    return {
        "uri": uri,
        "endpoint": url,
        "model": model,
        "supported": True,
        "status_code": resp.status_code,
        "dimensions": len(vec_a),
        "cosine_similarity": round(similarity, 6),
        "detail": "成功获取两段文本的 embedding 并计算余弦相似度",
        "error": None,
    }
