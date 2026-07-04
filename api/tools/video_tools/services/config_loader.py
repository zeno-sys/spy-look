"""加载 / 持久化 video_tools 运行时配置。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from config import VIDEO_TOOLS_CONFIG_PATH

_LEGACY_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
_CONFIG_PATH = VIDEO_TOOLS_CONFIG_PATH


def default_config() -> dict:
    from tools.video_tools.schemas import VideoToolsConfig

    return VideoToolsConfig().model_dump()


def _write_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ensure_config() -> None:
    """首次启动时写入默认配置；若存在旧版 services/config.json 则迁移。"""
    if _CONFIG_PATH.exists():
        return

    if _LEGACY_CONFIG_PATH.exists():
        with _LEGACY_CONFIG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = default_config()

    _write_config(data)


@lru_cache(maxsize=1)
def load_config() -> dict:
    ensure_config()
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def reload_config() -> dict:
    load_config.cache_clear()
    return load_config()


def save_config(data: dict) -> None:
    ensure_config()
    _write_config(data)
    load_config.cache_clear()
