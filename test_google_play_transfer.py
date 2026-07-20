import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import pro_user_db


class GooglePlayTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = pro_user_db.DB_PATH
        pro_user_db.DB_PATH = os.path.join(self.temp_dir.name, "app.sqlite3")
        pro_user_db.init_pro_user_db()

    def tearDown(self):
        pro_user_db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _future_expiry(self):
        return (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def test_moves_subscription_from_guest_to_google_and_preserves_guest_trial(self):
        guest_uid = "guest-uid"
        google_uid = "google-uid"
        token = "purchase-token"
        expiry = self._future_expiry()

        pro_user_db.start_trial(guest_uid)
        pro_user_db.set_google_subscription_user(
            guest_uid,
            product_id="safecontract_pro",
            purchase_token=token,
            subscription_state="SUBSCRIPTION_STATE_ACTIVE",
            pro_until=expiry,
        )

        pro_user_db.transfer_google_subscription_user(
            guest_uid,
            google_uid,
            product_id="safecontract_pro",
            purchase_token=token,
            subscription_state="SUBSCRIPTION_STATE_ACTIVE",
            pro_until=expiry,
        )

        guest = pro_user_db.get_pro_record(guest_uid)
        google = pro_user_db.get_pro_record(google_uid)

        self.assertIsNone(guest["purchase_token"])
        self.assertFalse(guest["paid_pro_active"])
        self.assertTrue(guest["trial_active"])
        self.assertEqual(guest["subscription_state"], "transferred")

        self.assertEqual(google["purchase_token"], token)
        self.assertTrue(google["paid_pro_active"])
        self.assertEqual(
            pro_user_db.get_uid_for_purchase_token(token),
            google_uid,
        )

    def test_rejects_transfer_if_expected_owner_is_stale(self):
        token = "purchase-token"
        expiry = self._future_expiry()

        pro_user_db.set_google_subscription_user(
            "real-owner",
            product_id="safecontract_pro",
            purchase_token=token,
            subscription_state="SUBSCRIPTION_STATE_ACTIVE",
            pro_until=expiry,
        )

        with self.assertRaisesRegex(ValueError, "owner changed"):
            pro_user_db.transfer_google_subscription_user(
                "stale-owner",
                "new-owner",
                product_id="safecontract_pro",
                purchase_token=token,
                subscription_state="SUBSCRIPTION_STATE_ACTIVE",
                pro_until=expiry,
            )

        self.assertEqual(
            pro_user_db.get_uid_for_purchase_token(token),
            "real-owner",
        )


if __name__ == "__main__":
    unittest.main()
