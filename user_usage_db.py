import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.abspath(
    os.getenv("APP_DB_PATH", os.path.join(os.path.dirname(__file__), "app.sqlite3"))
)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "2"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_free_usage (
                device_key TEXT PRIMARY KEY,
                free_used INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def upsert_user(uid: str, email: str | None, name: str | None, provider: str | None) -> None:
    now = _utcnow().isoformat()

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
    now = _utcnow().isoformat()

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


def ensure_device_usage(device_key: str, seed_used: int = 0) -> None:
    """Create a device counter and preserve the largest known legacy count."""
    now = _utcnow().isoformat()
    seed = max(0, int(seed_used or 0))

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO device_free_usage(device_key, free_used, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(device_key) DO UPDATE SET
                free_used = MAX(device_free_usage.free_used, excluded.free_used),
                updated_at = excluded.updated_at
            """,
            (device_key, seed, now),
        )
        conn.commit()


def get_device_free_used(device_key: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT free_used FROM device_free_usage WHERE device_key = ?",
            (device_key,),
        ).fetchone()
        return int(row["free_used"]) if row else 0


def increment_device_free_used(device_key: str) -> int:
    now = _utcnow().isoformat()

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT free_used FROM device_free_usage WHERE device_key = ?",
            (device_key,),
        ).fetchone()
        new_value = (int(row["free_used"]) if row else 0) + 1
        conn.execute(
            """
            INSERT INTO device_free_usage(device_key, free_used, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(device_key) DO UPDATE SET
                free_used = excluded.free_used,
                updated_at = excluded.updated_at
            """,
            (device_key, new_value, now),
        )
        conn.commit()
        return new_value


def purge_stale_device_usage(max_age_days: int = 730) -> int:
    """Remove pseudonymous anti-abuse counters after prolonged inactivity."""
    cutoff = (_utcnow() - timedelta(days=max(1, max_age_days))).isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM device_free_usage WHERE updated_at < ?",
            (cutoff,),
        )
        conn.commit()
        return int(cursor.rowcount or 0)


def delete_user_usage(uid: str) -> None:
    """Delete account-linked usage. Device anti-abuse counters are retained."""
    with get_conn() as conn:
        conn.execute("DELETE FROM free_usage WHERE uid = ?", (uid,))
        conn.execute("DELETE FROM users WHERE uid = ?", (uid,))
        conn.commit()
