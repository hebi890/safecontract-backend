import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.getenv("APP_DB_PATH", "app.sqlite3")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_pro_user_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pro_users (
                uid TEXT PRIMARY KEY,
                is_pro INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def is_pro_user(uid: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT is_pro FROM pro_users WHERE uid = ?",
            (uid,),
        ).fetchone()
        return bool(row["is_pro"]) if row else False


def set_pro_user(uid: str, source: str = "client_sync") -> None:
    now = datetime.utcnow().isoformat()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO pro_users(uid, is_pro, source, updated_at)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                is_pro = 1,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (uid, source, now),
        )
        conn.commit()
