import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

DB_PATH = os.getenv("APP_DB_PATH", "app.sqlite3")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _utcnow() -> datetime:
    return datetime.utcnow()


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except Exception:
        return None


def init_pro_user_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pro_users (
                uid TEXT PRIMARY KEY,
                is_pro INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                updated_at TEXT NOT NULL,
                trial_until TEXT,
                trial_started_at TEXT
            )
            """
        )

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(pro_users)").fetchall()
        }

        if "trial_until" not in columns:
            conn.execute("ALTER TABLE pro_users ADD COLUMN trial_until TEXT")

        if "trial_started_at" not in columns:
            conn.execute("ALTER TABLE pro_users ADD COLUMN trial_started_at TEXT")

        conn.commit()


def get_pro_record(uid: str) -> Dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT uid, is_pro, source, updated_at, trial_until, trial_started_at
            FROM pro_users
            WHERE uid = ?
            """,
            (uid,),
        ).fetchone()

    if not row:
        return {
            "uid": uid,
            "is_pro": False,
            "source": None,
            "updated_at": None,
            "trial_until": None,
            "trial_started_at": None,
            "trial_active": False,
        }

    trial_until = row["trial_until"]
    trial_dt = _parse_iso(trial_until)
    trial_active = bool(trial_dt and trial_dt > _utcnow())

    return {
        "uid": row["uid"],
        "is_pro": bool(row["is_pro"]),
        "source": row["source"],
        "updated_at": row["updated_at"],
        "trial_until": trial_until,
        "trial_started_at": row["trial_started_at"],
        "trial_active": trial_active,
    }


def get_trial_until(uid: str) -> Optional[str]:
    return get_pro_record(uid).get("trial_until")


def has_started_trial(uid: str) -> bool:
    record = get_pro_record(uid)
    return bool(record.get("trial_started_at"))


def is_pro_user(uid: str) -> bool:
    record = get_pro_record(uid)
    return bool(record["is_pro"] or record["trial_active"])


def set_pro_user(uid: str, source: str = "client_sync") -> None:
    now = _iso(_utcnow())

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO pro_users(uid, is_pro, source, updated_at, trial_until, trial_started_at)
            VALUES (?, 1, ?, ?, NULL, NULL)
            ON CONFLICT(uid) DO UPDATE SET
                is_pro = 1,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (uid, source, now),
        )
        conn.commit()


def start_trial(uid: str, days: int = 3, source: str = "trial_auto") -> Dict[str, Any]:
    now = _utcnow()
    now_iso = _iso(now)

    with get_conn() as conn:
        row = conn.execute(
            "SELECT trial_started_at, trial_until, is_pro FROM pro_users WHERE uid = ?",
            (uid,),
        ).fetchone()

        if row and row["trial_started_at"]:
            trial_until = row["trial_until"]
            trial_dt = _parse_iso(trial_until)
            return {
                "started": False,
                "trial_until": trial_until,
                "trial_active": bool(trial_dt and trial_dt > now),
                "is_pro": bool(row["is_pro"]) or bool(trial_dt and trial_dt > now),
            }

        trial_until_dt = now + timedelta(days=days)
        trial_until = _iso(trial_until_dt)

        conn.execute(
            """
            INSERT INTO pro_users(uid, is_pro, source, updated_at, trial_until, trial_started_at)
            VALUES (?, 0, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                source = excluded.source,
                updated_at = excluded.updated_at,
                trial_until = excluded.trial_until,
                trial_started_at = excluded.trial_started_at
            """,
            (uid, source, now_iso, trial_until, now_iso),
        )
        conn.commit()

    return {
        "started": True,
        "trial_until": trial_until,
        "trial_active": True,
        "is_pro": True,
    }
