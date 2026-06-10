import os
import json
import sqlite3
from typing import Any, Dict, List

DB_PATH = os.path.join(os.path.dirname(__file__), "history.sqlite3")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _table_columns(c: sqlite3.Cursor, table_name: str) -> set[str]:
    rows = c.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _history_table_exists(c: sqlite3.Cursor) -> bool:
    row = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
    ).fetchone()
    return row is not None


def _migrate_history_table_if_needed(conn: sqlite3.Connection) -> None:
    c = conn.cursor()

    if not _history_table_exists(c):
        return

    cols = _table_columns(c, "history")

    if "uid" not in cols:
        print("🔥 MIGRATION: adding uid column to history")
        c.execute("ALTER TABLE history ADD COLUMN uid TEXT NOT NULL DEFAULT 'legacy'")

    cols = _table_columns(c, "history")

    migrations = {
        "contract_type": "ALTER TABLE history ADD COLUMN contract_type TEXT",
        "pdf_path": "ALTER TABLE history ADD COLUMN pdf_path TEXT",
        "ai_json": "ALTER TABLE history ADD COLUMN ai_json TEXT",
        "content_hash": "ALTER TABLE history ADD COLUMN content_hash TEXT",
    }

    for col, sql in migrations.items():
        if col not in cols:
            print(f"🔥 MIGRATION: adding {col} column to history")
            c.execute(sql)

    conn.commit()


def init_db() -> None:
    print("🔥 INIT_DB RUNNING:", DB_PATH)

    conn = get_conn()
    c = conn.cursor()

    _migrate_history_table_if_needed(conn)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        uid TEXT NOT NULL,
        id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        file_name TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        full_text TEXT NOT NULL DEFAULT '',
        contract_type TEXT,
        pdf_path TEXT,
        risk TEXT NOT NULL DEFAULT 'warning',
        ai_json TEXT,
        content_hash TEXT,
        PRIMARY KEY (uid, id)
    )
    """)

    conn.commit()
    conn.close()


def upsert_history(item: Dict[str, Any]) -> None:
    conn = get_conn()
    c = conn.cursor()

    _migrate_history_table_if_needed(conn)

    c.execute("""
    INSERT INTO history (
        uid, id, created_at, file_name, summary, full_text,
        contract_type, pdf_path, risk, ai_json, content_hash
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(uid, id) DO UPDATE SET
        created_at=excluded.created_at,
        file_name=excluded.file_name,
        summary=excluded.summary,
        full_text=excluded.full_text,
        contract_type=excluded.contract_type,
        pdf_path=excluded.pdf_path,
        risk=excluded.risk,
        ai_json=COALESCE(excluded.ai_json, history.ai_json),
        content_hash=COALESCE(excluded.content_hash, history.content_hash)
    """, (
        str(item.get("uid", "")),
        str(item.get("id", "")),
        str(item.get("created_at", "")),
        str(item.get("file_name", "")),
        str(item.get("summary", "")),
        str(item.get("full_text", "")),
        item.get("contract_type"),
        item.get("pdf_path"),
        str(item.get("risk", "warning")),
        _json_or_none(item.get("ai_json")),
        item.get("content_hash"),
    ))

    conn.commit()
    conn.close()


def list_history(uid: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()

    _migrate_history_table_if_needed(conn)

    rows = c.execute("""
    SELECT *
    FROM history
    WHERE uid=?
    ORDER BY created_at DESC
    LIMIT ?
    """, (uid, limit)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def delete_history(uid: str, item_id: str) -> bool:
    conn = get_conn()
    c = conn.cursor()

    _migrate_history_table_if_needed(conn)

    cur = c.execute(
        "DELETE FROM history WHERE uid=? AND id=?",
        (uid, item_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_pdf_path(uid: str, item_id: str, pdf_path: str) -> bool:
    conn = get_conn()
    c = conn.cursor()

    _migrate_history_table_if_needed(conn)

    cur = c.execute(
        "UPDATE history SET pdf_path=? WHERE uid=? AND id=?",
        (pdf_path, uid, item_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def count_history(uid: str) -> int:
    conn = get_conn()
    c = conn.cursor()

    _migrate_history_table_if_needed(conn)

    c.execute("SELECT COUNT(*) AS cnt FROM history WHERE uid=?", (uid,))
    row = c.fetchone()
    conn.close()
    return int(row["cnt"] if row else 0)
