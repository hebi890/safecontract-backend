import sqlite3
from pathlib import Path

DB_FILE = Path("pro.sqlite3")


def init_pro_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pro_devices (
            device_id TEXT PRIMARY KEY,
            is_pro INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def set_pro_device(device_id: str, value: bool):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO pro_devices (device_id, is_pro)
        VALUES (?, ?)
        ON CONFLICT(device_id) DO UPDATE SET is_pro=excluded.is_pro
    """, (device_id, int(value)))

    conn.commit()
    conn.close()


def is_pro_device(device_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT is_pro FROM pro_devices WHERE device_id=?
    """, (device_id,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    return bool(row[0])