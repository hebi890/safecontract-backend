import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import user_usage_db


class DeviceFreeUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = user_usage_db.DB_PATH
        user_usage_db.DB_PATH = os.path.join(self.tmp.name, "app.sqlite3")
        user_usage_db.init_user_usage_db()

    def tearDown(self):
        user_usage_db.DB_PATH = self.original_path
        self.tmp.cleanup()

    def test_counter_survives_account_change_on_same_device(self):
        device = "hashed-device"
        user_usage_db.ensure_device_usage(device)
        self.assertEqual(user_usage_db.increment_device_free_used(device), 1)

        # A different Firebase UID must not create a fresh device allowance.
        user_usage_db.ensure_device_usage(device, seed_used=0)
        self.assertEqual(user_usage_db.get_device_free_used(device), 1)
        self.assertEqual(user_usage_db.increment_device_free_used(device), 2)
        self.assertEqual(user_usage_db.get_device_free_used(device), 2)

    def test_legacy_uid_count_seeds_device_without_decreasing_it(self):
        device = "hashed-device"
        user_usage_db.ensure_device_usage(device, seed_used=1)
        user_usage_db.increment_device_free_used(device)
        user_usage_db.ensure_device_usage(device, seed_used=0)
        self.assertEqual(user_usage_db.get_device_free_used(device), 2)

    def test_stale_pseudonymous_counter_is_purged(self):
        device = "stale-hashed-device"
        user_usage_db.ensure_device_usage(device, seed_used=2)
        old = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=731)
        ).isoformat()
        with sqlite3.connect(user_usage_db.DB_PATH) as conn:
            conn.execute(
                "UPDATE device_free_usage SET updated_at = ? WHERE device_key = ?",
                (old, device),
            )
            conn.commit()

        self.assertEqual(user_usage_db.purge_stale_device_usage(730), 1)
        self.assertEqual(user_usage_db.get_device_free_used(device), 0)


if __name__ == "__main__":
    unittest.main()
