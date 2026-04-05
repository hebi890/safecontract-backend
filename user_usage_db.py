import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.getenv("APP_DB_PATH", "app.sqlite3")
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "2"))


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_user_usage_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                uid TEXT PRIMARY KEY,
                email TEXT,
                name TEXT,
                provider TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS free_usage (
                uid TEXT PRIMARY KEY,
                free_used INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(uid) REFERENCES users(uid)
            )
            """
        )
        conn.commit()


def upsert_user(uid: str, email: str | None, name: str | None, provider: str | None) -> None:
    now = datetime.utcnow().isoformat()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users(uid, email, name, provider, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                provider = excluded.provider,
                last_seen_at = excluded.last_seen_at
            """,
            (uid, email, name, provider, now, now),
        )
        conn.execute(
            """
            INSERT INTO free_usage(uid, free_used, updated_at)
            VALUES (?, 0, ?)
            ON CONFLICT(uid) DO NOTHING
            """,
            (uid, now),
        )
        conn.commit()


def get_free_used(uid: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT free_used FROM free_usage WHERE uid = ?",
            (uid,),
        ).fetchone()
        return int(row["free_used"]) if row else 0


def get_free_left(uid: str) -> int:
    used = get_free_used(uid)
    return max(FREE_LIMIT - used, 0)


def can_use_free(uid: str) -> bool:
    return get_free_used(uid) < FREE_LIMIT


def increment_free_used(uid: str) -> int:
    now = datetime.utcnow().isoformat()

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            "SELECT free_used FROM free_usage WHERE uid = ?",
            (uid,),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO free_usage(uid, free_used, updated_at)
                VALUES (?, 1, ?)
                """,
                (uid, now),
            )
            conn.commit()
            return 1

        new_value = int(row["free_used"]) + 1
        conn.execute(
            """
            UPDATE free_usage
            SET free_used = ?, updated_at = ?
            WHERE uid = ?
            """,
            (new_value, now, uid),
        )
        conn.commit()
        return new_value
