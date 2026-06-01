from __future__ import annotations

import json
import logging
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

APP_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
LEGACY_UNKNOWN_APP_ID = "unknown"

logger = logging.getLogger("spy_look")
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PACKAGE_ROOT / "spy_look.db"

CREATE_LOGS_SQL = """
CREATE TABLE IF NOT EXISTS spy_look_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT,
    model TEXT,
    status_code INTEGER,
    latency_ms INTEGER,
    client_ip TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    request_body TEXT,
    response_body TEXT,
    session_id TEXT NOT NULL DEFAULT 'default',
    app_id TEXT NOT NULL DEFAULT 'unknown',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_UPSTREAMS_SQL = """
CREATE TABLE IF NOT EXISTS spy_look_upstreams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT NOT NULL,
    trust_env INTEGER NOT NULL DEFAULT 0,
    timeout_seconds REAL NOT NULL DEFAULT 60.0,
    enabled INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CLIENT_KEYS_SQL = """
CREATE TABLE IF NOT EXISTS spy_look_client_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key TEXT NOT NULL UNIQUE,
    app_id TEXT NOT NULL UNIQUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PENDING_GATEWAY_KEYS_SQL = """
CREATE TABLE IF NOT EXISTS spy_look_pending_gateway_keys (
    api_key TEXT PRIMARY KEY,
    expires_at REAL NOT NULL
);
"""


def validate_app_id(raw: str) -> str:
    text = str(raw or "").strip()
    if not text or not APP_ID_RE.fullmatch(text):
        raise ValueError(
            "app_id 须为 1–64 位，以字母或数字开头，仅可含字母、数字、点、下划线、连字符"
        )
    return text


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    key_cols = _table_columns(conn, "spy_look_client_keys")
    if "app_id" not in key_cols:
        conn.execute("ALTER TABLE spy_look_client_keys ADD COLUMN app_id TEXT")
    log_cols = _table_columns(conn, "spy_look_logs")
    if "app_id" not in log_cols:
        conn.execute(
            "ALTER TABLE spy_look_logs ADD COLUMN app_id TEXT NOT NULL DEFAULT 'unknown'"
        )
    conn.execute(
        """
        UPDATE spy_look_logs
        SET app_id = ?
        WHERE app_id IS NULL OR app_id = ''
        """,
        (LEGACY_UNKNOWN_APP_ID,),
    )
    legacy_rows = conn.execute(
        """
        SELECT id FROM spy_look_client_keys
        WHERE app_id IS NULL OR app_id = ''
        """
    ).fetchall()
    for (key_id,) in legacy_rows:
        conn.execute(
            "UPDATE spy_look_client_keys SET app_id = ? WHERE id = ?",
            (f"legacy-key-{key_id}", key_id),
        )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_spy_look_client_keys_app_id
        ON spy_look_client_keys (app_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_spy_look_logs_app_created
        ON spy_look_logs (app_id, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_spy_look_logs_app_session
        ON spy_look_logs (app_id, session_id)
        """
    )


def setup_logging() -> None:
    if logger.handlers:
        _init_db()
        return
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _init_db()


def log_event(event: dict[str, Any]) -> None:
    logger.info(json.dumps(event, ensure_ascii=False, default=str))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO spy_look_logs (
                path, model, status_code, latency_ms, client_ip,
                input_tokens, output_tokens, total_tokens,
                request_body, response_body, session_id, app_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("path"),
                event.get("model"),
                event.get("status_code"),
                event.get("latency_ms"),
                event.get("client_ip"),
                event.get("input_tokens"),
                event.get("output_tokens"),
                event.get("total_tokens"),
                _to_json_text(event.get("request_body")),
                _to_json_text(event.get("response_body")),
                event.get("session_id") or "default",
                event.get("app_id") or LEGACY_UNKNOWN_APP_ID,
            ),
        )


def _like_contains(needle: str) -> str:
    """子串匹配 path（兼容旧短 path 与新存完整 URL）；LIKE 元字符已转义。"""
    esc = (
        str(needle)
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{esc}%"


def query_logs(
    *,
    path: str | None = None,
    model: str | None = None,
    client_ip: str | None = None,
    app_id: str | None = None,
    session_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql = """
    SELECT
        id, path, model, status_code, latency_ms, client_ip,
        input_tokens, output_tokens, total_tokens,
        request_body, response_body, session_id, app_id, created_at
    FROM spy_look_logs
    """
    clauses: list[str] = []
    params: list[Any] = []

    if path is not None and str(path).strip():
        clauses.append("path LIKE ? ESCAPE '\\'")
        params.append(_like_contains(str(path).strip()))
    if model:
        clauses.append("model = ?")
        params.append(model)
    if client_ip:
        clauses.append("client_ip = ?")
        params.append(client_ip)
    if app_id:
        clauses.append("app_id = ?")
        params.append(app_id)
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if start_time:
        clauses.append("created_at >= ?")
        params.append(_normalize_datetime(start_time))
    if end_time:
        clauses.append("created_at <= ?")
        params.append(_normalize_datetime(end_time))

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    sort_column = _normalize_order_by(order_by)
    sort_direction = "ASC" if order_dir.lower() == "asc" else "DESC"
    sql += f" ORDER BY {sort_column} {sort_direction} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def delete_log(log_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM spy_look_logs WHERE id = ?", (log_id,))
        return cur.rowcount > 0


def delete_logs_by_app(app_id: str) -> int:
    aid = str(app_id or "").strip()
    if not aid:
        raise ValueError("app_id is required")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM spy_look_logs WHERE app_id = ?", (aid,))
        return int(cur.rowcount)


def delete_logs_by_session(app_id: str, session_id: str) -> int:
    aid = str(app_id or "").strip()
    sid = str(session_id or "").strip()
    if not aid:
        raise ValueError("app_id is required")
    if not sid:
        raise ValueError("session_id is required")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "DELETE FROM spy_look_logs WHERE app_id = ? AND session_id = ?",
            (aid, sid),
        )
        return int(cur.rowcount)


def list_log_apps(
    *, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """Distinct app_id with counts; paginated."""
    count_sql = "SELECT COUNT(DISTINCT app_id) FROM spy_look_logs"
    data_sql = """
    SELECT
        app_id,
        COUNT(*) AS log_count,
        MIN(created_at) AS first_created_at,
        MAX(created_at) AS last_created_at,
        COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
        COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
        COALESCE(SUM(total_tokens), 0) AS total_total_tokens
    FROM spy_look_logs
    GROUP BY app_id
    ORDER BY last_created_at DESC
    LIMIT ? OFFSET ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total = int(conn.execute(count_sql).fetchone()[0])
        rows = conn.execute(data_sql, (limit, offset)).fetchall()
    return [dict(row) for row in rows], total


def list_log_sessions(
    *, app_id: str, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """Distinct session_id for one app_id; paginated."""
    aid = validate_app_id(app_id)
    count_sql = (
        "SELECT COUNT(DISTINCT session_id) FROM spy_look_logs WHERE app_id = ?"
    )
    data_sql = """
    SELECT
        session_id,
        COUNT(*) AS log_count,
        MIN(created_at) AS first_created_at,
        MAX(created_at) AS last_created_at,
        COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
        COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
        COALESCE(SUM(total_tokens), 0) AS total_total_tokens
    FROM spy_look_logs
    WHERE app_id = ?
    GROUP BY session_id
    ORDER BY last_created_at DESC
    LIMIT ? OFFSET ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total = int(conn.execute(count_sql, (aid,)).fetchone()[0])
        rows = conn.execute(data_sql, (aid, limit, offset)).fetchall()
    return [dict(row) for row in rows], total


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_LOGS_SQL)
        conn.execute(CREATE_UPSTREAMS_SQL)
        conn.execute(CREATE_CLIENT_KEYS_SQL)
        conn.execute(CREATE_PENDING_GATEWAY_KEYS_SQL)
        _migrate_schema(conn)


def _client_keys_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM spy_look_client_keys").fetchone()[0])


def get_client_api_key() -> str:
    """返回列表中的第一条完整密钥（供本机 client-info 等展示与探测）。"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT api_key FROM spy_look_client_keys ORDER BY id ASC LIMIT 1"
        ).fetchone()
    if row and str(row[0] or "").strip():
        return str(row[0])
    return ""


def get_client_api_key_meta() -> dict[str, Any]:
    items = list_client_keys_meta()
    first_mask = items[0]["api_key_masked"] if items else ""
    return {
        "items": items,
        "gateway_api_key_masked": first_mask,
    }


def list_client_keys_meta() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, api_key, app_id, created_at
            FROM spy_look_client_keys
            ORDER BY id ASC
            """
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        raw = str(d.pop("api_key") or "")
        d["api_key_masked"] = mask_api_key(raw)
        out.append(d)
    return out


def get_client_key_plain(key_id: int) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT api_key FROM spy_look_client_keys WHERE id = ?", (key_id,)
        ).fetchone()
    if not row:
        return None
    return str(row[0] or "")


def resolve_app_id_by_api_key(provided_key: str) -> str | None:
    text = str(provided_key or "").strip()
    if not text:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT app_id FROM spy_look_client_keys WHERE api_key = ? LIMIT 1",
            (text,),
        ).fetchone()
    if not row:
        return None
    app_id = str(row[0] or "").strip()
    return app_id or LEGACY_UNKNOWN_APP_ID


def client_api_key_is_valid(provided_key: str) -> bool:
    return resolve_app_id_by_api_key(provided_key) is not None


def generate_gateway_api_key() -> str:
    """生成对外网关 API Key（OpenAI 风格前缀 + 随机段）。"""
    return f"sk-spy-{secrets.token_urlsafe(32)}"


_PENDING_GATEWAY_KEY_TTL_SEC = 600


def _prune_pending_gateway_keys(conn: sqlite3.Connection, now: float | None = None) -> None:
    ts = time.time() if now is None else now
    conn.execute(
        "DELETE FROM spy_look_pending_gateway_keys WHERE expires_at < ?",
        (ts,),
    )


def register_pending_gateway_key(key: str) -> None:
    """登记服务端刚生成的 Key（存 SQLite，多 worker 共享）；供保存时一次性消费。"""
    text = str(key or "").strip()
    if not text:
        return
    expires_at = time.time() + _PENDING_GATEWAY_KEY_TTL_SEC
    with sqlite3.connect(DB_PATH) as conn:
        _prune_pending_gateway_keys(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO spy_look_pending_gateway_keys (api_key, expires_at)
            VALUES (?, ?)
            """,
            (text, expires_at),
        )


def consume_pending_gateway_key(key: str) -> bool:
    """保存时校验并消费 pending Key；DELETE 原子操作避免多 worker 重复入库。"""
    text = str(key or "").strip()
    if not text:
        return False
    now = time.time()
    with sqlite3.connect(DB_PATH) as conn:
        _prune_pending_gateway_keys(conn, now)
        cur = conn.execute(
            """
            DELETE FROM spy_look_pending_gateway_keys
            WHERE api_key = ? AND expires_at >= ?
            """,
            (text, now),
        )
        return cur.rowcount > 0


def add_client_key(api_key: str, app_id: str) -> int:
    text = str(api_key or "").strip()
    if not text:
        raise ValueError("api_key must be non-empty")
    aid = validate_app_id(app_id)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO spy_look_client_keys (api_key, app_id) VALUES (?, ?)",
                (text, aid),
            )
            return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        msg = str(exc).lower()
        if "app_id" in msg:
            raise ValueError("该 app_id 已存在") from exc
        raise ValueError("该 API Key 已存在") from exc


def update_client_key_app_id(key_id: int, app_id: str) -> None:
    aid = validate_app_id(app_id)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "UPDATE spy_look_client_keys SET app_id = ? WHERE id = ?",
                (aid, key_id),
            )
            if cur.rowcount == 0:
                raise LookupError("client key not found")
    except sqlite3.IntegrityError as exc:
        raise ValueError("该 app_id 已存在") from exc


def delete_client_key(key_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        n = _client_keys_count(conn)
        if n == 1:
            raise ValueError("至少保留一条对外 API Key")
        cur = conn.execute("DELETE FROM spy_look_client_keys WHERE id = ?", (key_id,))
        if cur.rowcount == 0:
            raise LookupError("client key not found")


def _to_json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _normalize_datetime(value: str) -> str:
    text = value.strip().replace("T", " ")
    if len(text) == 16:
        return f"{text}:00"
    return text


def _normalize_order_by(value: str) -> str:
    allowed = {"created_at", "latency_ms", "status_code"}
    return value if value in allowed else "created_at"


def mask_api_key(api_key: str) -> str:
    """脱敏：保留首尾各 4 位，中间固定为 ****（避免长 Key 撑满表格）。"""
    text = str(api_key or "").strip()
    if not text:
        return ""
    n = len(text)
    if n <= 8:
        return "*" * min(n, 4)
    keep = 4
    return f"{text[:keep]}****{text[-keep:]}"


def _upstream_row_public(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    key = str(d.get("api_key") or "")
    d.pop("api_key", None)
    d["api_key_masked"] = mask_api_key(key)
    d["trust_env"] = bool(d.get("trust_env"))
    d["enabled"] = bool(d.get("enabled"))
    d["is_default"] = bool(d.get("is_default"))
    return d


def list_upstreams() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM spy_look_upstreams ORDER BY is_default DESC, id ASC"
        ).fetchall()
    return [_upstream_row_public(r) for r in rows]


def list_failover_upstream_rows() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM spy_look_upstreams WHERE enabled = 1 ORDER BY is_default DESC, id ASC"
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        d["trust_env"] = bool(d.get("trust_env"))
        d["enabled"] = bool(d.get("enabled"))
        d["is_default"] = bool(d.get("is_default"))
        result.append(d)
    return result


def get_upstream(upstream_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM spy_look_upstreams WHERE id = ?", (upstream_id,)
        ).fetchone()
    return _upstream_row_public(row) if row else None


def get_upstream_runtime(upstream_id: int) -> dict[str, Any] | None:
    """Full row dict including api_key for building httpx client."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM spy_look_upstreams WHERE id = ?", (upstream_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["trust_env"] = bool(d.get("trust_env"))
    d["enabled"] = bool(d.get("enabled"))
    d["is_default"] = bool(d.get("is_default"))
    return d


def get_default_upstream_row() -> dict[str, Any] | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM spy_look_upstreams
            WHERE enabled = 1 AND is_default = 1
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if row:
            d = dict(row)
            d["trust_env"] = bool(d.get("trust_env"))
            d["enabled"] = bool(d.get("enabled"))
            d["is_default"] = bool(d.get("is_default"))
            return d
        row = conn.execute(
            """
            SELECT * FROM spy_look_upstreams
            WHERE enabled = 1
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["trust_env"] = bool(d.get("trust_env"))
        d["enabled"] = bool(d.get("enabled"))
        d["is_default"] = bool(d.get("is_default"))
        return d


def create_upstream(
    *,
    name: str,
    base_url: str,
    api_key: str,
    trust_env: bool = False,
    timeout_seconds: float = 60.0,
    enabled: bool = True,
    is_default: bool = False,
) -> int:
    te = 1 if trust_env else 0
    en = 1 if enabled else 0
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO spy_look_upstreams (
                name, base_url, api_key, trust_env, timeout_seconds, enabled, is_default
            ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                name.strip(),
                base_url.strip(),
                api_key,
                te,
                float(timeout_seconds),
                en,
            ),
        )
        new_id = int(cur.lastrowid)
        has_default = (
            int(
                conn.execute(
                    "SELECT COUNT(*) FROM spy_look_upstreams WHERE is_default = 1"
                ).fetchone()[0]
            )
            > 0
        )
        if is_default or not has_default:
            conn.execute(
                "UPDATE spy_look_upstreams SET is_default = 0, updated_at = CURRENT_TIMESTAMP"
            )
            conn.execute(
                """
                UPDATE spy_look_upstreams
                SET is_default = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_id,),
            )
    return new_id


def update_upstream(
    upstream_id: int,
    *,
    name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    trust_env: bool | None = None,
    timeout_seconds: float | None = None,
    enabled: bool | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if name is not None:
        fields.append("name = ?")
        params.append(name.strip())
    if base_url is not None:
        fields.append("base_url = ?")
        params.append(base_url.strip())
    if api_key is not None and str(api_key).strip():
        fields.append("api_key = ?")
        params.append(str(api_key).strip())
    if trust_env is not None:
        fields.append("trust_env = ?")
        params.append(1 if trust_env else 0)
    if timeout_seconds is not None:
        fields.append("timeout_seconds = ?")
        params.append(float(timeout_seconds))
    if enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if enabled else 0)
    if not fields:
        return True
    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(upstream_id)
    sql = f"UPDATE spy_look_upstreams SET {', '.join(fields)} WHERE id = ?"
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount > 0


def delete_upstream(upstream_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT is_default FROM spy_look_upstreams WHERE id = ?", (upstream_id,)
        ).fetchone()
        if not row:
            return False
        was_default = int(row[0]) == 1
        conn.execute("DELETE FROM spy_look_upstreams WHERE id = ?", (upstream_id,))
        if was_default:
            nxt = conn.execute(
                "SELECT id FROM spy_look_upstreams ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if nxt:
                conn.execute(
                    "UPDATE spy_look_upstreams SET is_default = 0, updated_at = CURRENT_TIMESTAMP"
                )
                conn.execute(
                    """
                    UPDATE spy_look_upstreams
                    SET is_default = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (int(nxt[0]),),
                )
    return True


def set_default_upstream(upstream_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM spy_look_upstreams WHERE id = ? AND enabled = 1",
            (upstream_id,),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE spy_look_upstreams SET is_default = 0, updated_at = CURRENT_TIMESTAMP"
        )
        conn.execute(
            """
            UPDATE spy_look_upstreams
            SET is_default = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (upstream_id,),
        )
    return True
