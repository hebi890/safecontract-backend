import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import google_play_verifier


class GooglePlayVerifierTests(unittest.TestCase):
    def _verify(self, state: str, expiry: datetime):
        response = {
            "subscriptionState": state,
            "latestOrderId": "GPA.test",
            "lineItems": [
                {
                    "productId": google_play_verifier.DEFAULT_PRODUCT_ID,
                    "expiryTime": expiry.isoformat().replace("+00:00", "Z"),
                }
            ],
        }
        service = MagicMock()
        service.purchases.return_value.subscriptionsv2.return_value.get.return_value.execute.return_value = response

        with patch.object(
            google_play_verifier,
            "_android_publisher_service",
            return_value=service,
        ):
            return google_play_verifier.verify_google_play_subscription(
                package_name=google_play_verifier.DEFAULT_PACKAGE_NAME,
                product_id=google_play_verifier.DEFAULT_PRODUCT_ID,
                purchase_token="test-token",
            )

    def test_canceled_subscription_keeps_access_until_expiry(self):
        result = self._verify(
            "SUBSCRIPTION_STATE_CANCELED",
            datetime.now(timezone.utc) + timedelta(days=3),
        )
        self.assertTrue(result["ok"])

    def test_canceled_subscription_loses_access_after_expiry(self):
        result = self._verify(
            "SUBSCRIPTION_STATE_CANCELED",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "SUBSCRIPTION_NOT_ACTIVE")


if __name__ == "__main__":
    unittest.main()
