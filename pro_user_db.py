import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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
    # Store UTC as ISO without microseconds. Existing DB used naive UTC strings,
    # so we keep that format for compatibility.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.replace(microsecond=0)
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
                trial_started_at TEXT,
                pro_until TEXT,
                product_id TEXT,
                purchase_token TEXT,
                subscription_state TEXT,
                order_id TEXT
            )
            """
        )

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(pro_users)").fetchall()
        }

        migrations = {
            "trial_until": "ALTER TABLE pro_users ADD COLUMN trial_until TEXT",
            "trial_started_at": "ALTER TABLE pro_users ADD COLUMN trial_started_at TEXT",
            "pro_until": "ALTER TABLE pro_users ADD COLUMN pro_until TEXT",
            "product_id": "ALTER TABLE pro_users ADD COLUMN product_id TEXT",
            "purchase_token": "ALTER TABLE pro_users ADD COLUMN purchase_token TEXT",
            "subscription_state": "ALTER TABLE pro_users ADD COLUMN subscription_state TEXT",
            "order_id": "ALTER TABLE pro_users ADD COLUMN order_id TEXT",
        }

        for column, sql in migrations.items():
            if column not in columns:
                conn.execute(sql)

        conn.commit()


def get_pro_record(uid: str) -> Dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT uid, is_pro, source, updated_at, trial_until, trial_started_at,
                   pro_until, product_id, purchase_token, subscription_state, order_id
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
            "pro_until": None,
            "paid_pro_active": False,
            "product_id": None,
            "purchase_token": None,
            "subscription_state": None,
            "order_id": None,
        }

    trial_until = row["trial_until"]
    trial_dt = _parse_iso(trial_until)
    trial_active = bool(trial_dt and trial_dt > _utcnow())

    pro_until = row["pro_until"]
    pro_dt = _parse_iso(pro_until)

    # If pro_until is NULL, we keep old/dev/lifetime records working.
    # New Google Play subscriptions should always set pro_until.
    paid_pro_active = bool(row["is_pro"]) and (pro_dt is None or pro_dt > _utcnow())

    return {
        "uid": row["uid"],
        "is_pro": bool(row["is_pro"]),
        "source": row["source"],
        "updated_at": row["updated_at"],
        "trial_until": trial_until,
        "trial_started_at": row["trial_started_at"],
        "trial_active": trial_active,
        "pro_until": pro_until,
        "paid_pro_active": paid_pro_active,
        "product_id": row["product_id"],
        "purchase_token": row["purchase_token"],
        "subscription_state": row["subscription_state"],
        "order_id": row["order_id"],
    }


def get_trial_until(uid: str) -> Optional[str]:
    return get_pro_record(uid).get("trial_until")


def has_started_trial(uid: str) -> bool:
    record = get_pro_record(uid)
    return bool(record.get("trial_started_at"))


def is_paid_pro_user(uid: str) -> bool:
    return bool(get_pro_record(uid).get("paid_pro_active"))


def is_pro_user(uid: str) -> bool:
    record = get_pro_record(uid)
    return bool(record.get("paid_pro_active") or record.get("trial_active"))


def set_pro_user(uid: str, source: str = "client_sync") -> None:
    """Legacy/dev helper. Do not expose publicly in production."""
    now = _iso(_utcnow())

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO pro_users(uid, is_pro, source, updated_at, trial_until, trial_started_at,
                                  pro_until, product_id, purchase_token, subscription_state, order_id)
            VALUES (?, 1, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
            ON CONFLICT(uid) DO UPDATE SET
                is_pro = 1,
                source = excluded.source,
                updated_at = excluded.updated_at,
                pro_until = NULL
            """,
            (uid, source, now),
        )
        conn.commit()


def set_google_subscription_user(
    uid: str,
    *,
    product_id: str,
    purchase_token: str,
    subscription_state: str,
    pro_until: str,
    order_id: Optional[str] = None,
    source: str = "google_play",
) -> None:
    now = _iso(_utcnow())

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO pro_users(uid, is_pro, source, updated_at, trial_until, trial_started_at,
                                  pro_until, product_id, purchase_token, subscription_state, order_id)
            VALUES (?, 1, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                is_pro = 1,
                source = excluded.source,
                updated_at = excluded.updated_at,
                pro_until = excluded.pro_until,
                product_id = excluded.product_id,
                purchase_token = excluded.purchase_token,
                subscription_state = excluded.subscription_state,
                order_id = excluded.order_id
            """,
            (uid, source, now, pro_until, product_id, purchase_token, subscription_state, order_id),
        )
        conn.commit()


def clear_paid_pro_if_expired(uid: str) -> None:
    record = get_pro_record(uid)
    pro_dt = _parse_iso(record.get("pro_until"))
    if record.get("is_pro") and pro_dt is not None and pro_dt <= _utcnow():
        now = _iso(_utcnow())
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE pro_users
                SET is_pro = 0, updated_at = ?, subscription_state = ?
                WHERE uid = ?
                """,
                (now, "expired", uid),
            )
            conn.commit()


def get_uid_for_purchase_token(purchase_token: str) -> Optional[str]:
    token = (purchase_token or "").strip()
    if not token:
        return None

    with get_conn() as conn:
        row = conn.execute(
            "SELECT uid FROM pro_users WHERE purchase_token = ? LIMIT 1",
            (token,),
        ).fetchone()

    return row["uid"] if row else None


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
