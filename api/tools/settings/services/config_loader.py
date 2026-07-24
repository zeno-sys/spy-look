"""加载 / 持久化全局设置（JSON 文件，不入库）。"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from config import SETTINGS_CONFIG_PATH

_CONFIG_PATH = SETTINGS_CONFIG_PATH


def default_config() -> dict[str, Any]:
    from tools.settings.schemas import AppSettings

    return AppSettings().model_dump()


def _write_config(data: dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ensure_config() -> None:
    if _CONFIG_PATH.exists():
        return
    _write_config(default_config())


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    ensure_config()
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    # 与默认结构合并，兼容旧文件缺字段
    merged = default_config()
    if isinstance(raw, dict):
        llm = raw.get("llm")
        if isinstance(llm, dict):
            merged["llm"] = {**merged["llm"], **llm}
    return merged


def reload_config() -> dict[str, Any]:
    load_config.cache_clear()
    return load_config()


def save_config(data: dict[str, Any]) -> None:
    ensure_config()
    _write_config(data)
    load_config.cache_clear()
