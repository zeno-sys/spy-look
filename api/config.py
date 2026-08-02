from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent

# Docker / 生产可用 SPY_LOOK_DATA_DIR 把 SQLite 与运行时配置放到持久卷
_data_dir_env = (os.environ.get("SPY_LOOK_DATA_DIR") or "").strip()
DATA_DIR = Path(_data_dir_env).expanduser().resolve() if _data_dir_env else PACKAGE_ROOT
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "spy_look.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# 媒体工具运行时配置（由管理界面读写，不入库）
VIDEO_TOOLS_CONFIG_PATH = DATA_DIR / "video_tools_config.json"

# 全局设置（大模型等，由设置页读写，不入库）
SETTINGS_CONFIG_PATH = DATA_DIR / "settings_config.json"

UI_DIR = PACKAGE_ROOT.parent / "ui" / "dist"

DEFAULT_LOG_SESSION_ID = "default"
LEGACY_UNKNOWN_APP_ID = "unknown"
