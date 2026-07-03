from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
DB_PATH = PACKAGE_ROOT / "spy_look.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

UI_DIR = PACKAGE_ROOT.parent / "ui" / "dist"

DEFAULT_LOG_SESSION_ID = "default"
LEGACY_UNKNOWN_APP_ID = "unknown"
