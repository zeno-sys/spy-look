from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
DB_PATH = PACKAGE_ROOT / "spy_look.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# 视频工具运行时配置（由管理界面读写，不入库）
VIDEO_TOOLS_CONFIG_PATH = PACKAGE_ROOT / "video_tools_config.json"

# 全局设置（大模型等，由设置页读写，不入库）
SETTINGS_CONFIG_PATH = PACKAGE_ROOT / "settings_config.json"

UI_DIR = PACKAGE_ROOT.parent / "ui" / "dist"

DEFAULT_LOG_SESSION_ID = "default"
LEGACY_UNKNOWN_APP_ID = "unknown"
