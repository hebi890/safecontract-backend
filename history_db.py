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

    # 🔥 NOWA STRUKTURA — UID zamiast device_id
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
        item.get("ai_json"),
        item.get("content_hash"),
    ))

    conn.commit()
    conn.close()


def list_history(uid: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()

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

    c.execute("SELECT COUNT(*) AS cnt FROM history WHERE uid=?", (uid,))
    row = c.fetchone()
    conn.close()
    return int(row["cnt"] if row else 0)