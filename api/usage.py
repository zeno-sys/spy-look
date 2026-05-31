from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

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
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


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
                request_body, response_body, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        request_body, response_body, session_id, created_at
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


def list_log_sessions(
    *, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """Distinct session_id with counts; paginated. Returns (rows, total_distinct_sessions)."""
    count_sql = "SELECT COUNT(DISTINCT session_id) FROM spy_look_logs"
    data_sql = """
    SELECT
        session_id,
        COUNT(*) AS log_count,
        MIN(created_at) AS first_created_at,
        MAX(created_at) AS last_created_at
    FROM spy_look_logs
    GROUP BY session_id
    ORDER BY last_created_at DESC
    LIMIT ? OFFSET ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total = int(conn.execute(count_sql).fetchone()[0])
        rows = conn.execute(data_sql, (limit, offset)).fetchall()
    return [dict(row) for row in rows], total


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_LOGS_SQL)
        conn.execute(CREATE_UPSTREAMS_SQL)
        conn.execute(CREATE_CLIENT_KEYS_SQL)


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
            SELECT id, api_key, created_at
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


def client_api_key_is_valid(provided_key: str) -> bool:
    text = str(provided_key or "").strip()
    if not text:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM spy_look_client_keys WHERE api_key = ? LIMIT 1",
            (text,),
        ).fetchone()
    return row is not None


def add_client_key(api_key: str) -> int:
    text = str(api_key or "").strip()
    if not text:
        raise ValueError("api_key must be non-empty")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO spy_look_client_keys (api_key) VALUES (?)", (text,)
            )
            return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ValueError("该 API Key 已存在") from exc


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
    text = str(api_key or "").strip()
    if not text:
        return ""
    if len(text) <= 10:
        return "***"
    return f"{text[:4]}…{text[-4:]}"


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
