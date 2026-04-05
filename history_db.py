import os
import sqlite3
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "history.sqlite3")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        device_id TEXT NOT NULL,
        id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        file_name TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        full_text TEXT NOT NULL DEFAULT '',
        contract_type TEXT,
        pdf_path TEXT,
        risk TEXT NOT NULL DEFAULT 'warning',
        free_used INTEGER NOT NULL DEFAULT 0,
        ai_json TEXT,
        content_hash TEXT,
        PRIMARY KEY (device_id, id)
    )
    """)
    conn.commit()

    try:
        c.execute("ALTER TABLE history ADD COLUMN free_used INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE history ADD COLUMN ai_json TEXT")
        conn.commit()
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE history ADD COLUMN content_hash TEXT")
        conn.commit()
    except Exception:
        pass

    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_history_content_hash ON history(content_hash)")
        conn.commit()
    except Exception:
        pass

    conn.close()


def upsert_history(item: Dict[str, Any]) -> None:
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    INSERT INTO history (
        device_id, id, created_at, file_name, summary, full_text,
        contract_type, pdf_path, risk, free_used, ai_json, content_hash
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(device_id, id) DO UPDATE SET
        created_at=excluded.created_at,
        file_name=excluded.file_name,
        summary=excluded.summary,
        full_text=excluded.full_text,
        contract_type=excluded.contract_type,
        pdf_path=excluded.pdf_path,
        risk=excluded.risk,
        free_used=excluded.free_used,
        ai_json=COALESCE(excluded.ai_json, history.ai_json),
        content_hash=COALESCE(excluded.content_hash, history.content_hash)
    """, (
        str(item.get("device_id", "")),
        str(item.get("id", "")),
        str(item.get("created_at", "")),
        str(item.get("file_name", "")),
        str(item.get("summary", "")),
        str(item.get("full_text", "")),
        item.get("contract_type"),
        item.get("pdf_path"),
        str(item.get("risk", "warning")),
        int(item.get("free_used", 0) or 0),
        item.get("ai_json"),
        item.get("content_hash"),
    ))

    conn.commit()
    conn.close()


def list_history(device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()

    rows = c.execute("""
    SELECT *
    FROM history
    WHERE device_id=?
    ORDER BY created_at DESC
    LIMIT ?
    """, (device_id, limit)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def get_history_item(device_id: str, item_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()

    row = c.execute("""
    SELECT *
    FROM history
    WHERE device_id=? AND id=?
    LIMIT 1
    """, (device_id, item_id)).fetchone()

    conn.close()
    return dict(row) if row else None


def find_cached_ai_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    if not content_hash:
        return None

    conn = get_conn()
    c = conn.cursor()

    row = c.execute("""
    SELECT *
    FROM history
    WHERE content_hash=? AND ai_json IS NOT NULL AND ai_json != ''
    ORDER BY created_at DESC
    LIMIT 1
    """, (content_hash,)).fetchone()

    conn.close()
    return dict(row) if row else None


def delete_history(device_id: str, item_id: str) -> bool:
    conn = get_conn()
    c = conn.cursor()

    cur = c.execute(
        "DELETE FROM history WHERE device_id=? AND id=?",
        (device_id, item_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_pdf_path(device_id: str, item_id: str, pdf_path: str) -> bool:
    conn = get_conn()
    c = conn.cursor()

    cur = c.execute(
        "UPDATE history SET pdf_path=? WHERE device_id=? AND id=?",
        (pdf_path, device_id, item_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_ai_json(device_id: str, item_id: str, ai_json: str) -> bool:
    conn = get_conn()
    c = conn.cursor()

    cur = c.execute(
        "UPDATE history SET ai_json=? WHERE device_id=? AND id=?",
        (ai_json, device_id, item_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_content_hash(device_id: str, item_id: str, content_hash: str) -> bool:
    conn = get_conn()
    c = conn.cursor()

    cur = c.execute(
        "UPDATE history SET content_hash=? WHERE device_id=? AND id=?",
        (content_hash, device_id, item_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def count_history(device_id: str) -> int:
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) AS cnt FROM history WHERE device_id=?", (device_id,))
    row = c.fetchone()
    conn.close()
    return int(row["cnt"] if row else 0)
