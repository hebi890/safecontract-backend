import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ANDROID_PUBLISHER_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
DEFAULT_PACKAGE_NAME = os.getenv("GOOGLE_PLAY_PACKAGE_NAME", "pl.umownia.umownia")
DEFAULT_PRODUCT_ID = os.getenv("GOOGLE_PLAY_PRO_PRODUCT_ID", "safecontract_pro")

ACTIVE_STATES = {
    "SUBSCRIPTION_STATE_ACTIVE",
    "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
}


def _credentials():
    raw_json = os.getenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON")
    file_path = os.getenv("GOOGLE_PLAY_SERVICE_ACCOUNT_FILE")

    if raw_json:
        info = json.loads(raw_json)
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=[ANDROID_PUBLISHER_SCOPE],
        )

    if file_path:
        return service_account.Credentials.from_service_account_file(
            file_path,
            scopes=[ANDROID_PUBLISHER_SCOPE],
        )

    raise RuntimeError(
        "Missing Google Play credentials. Set GOOGLE_PLAY_SERVICE_ACCOUNT_JSON "
        "or GOOGLE_PLAY_SERVICE_ACCOUNT_FILE."
    )


def _android_publisher_service():
    return build(
        "androidpublisher",
        "v3",
        credentials=_credentials(),
        cache_discovery=False,
    )


def _parse_google_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def verify_google_play_subscription(
    *,
    package_name: str,
    product_id: str,
    purchase_token: str,
) -> Dict[str, Any]:
    package_name = (package_name or DEFAULT_PACKAGE_NAME).strip()
    product_id = (product_id or DEFAULT_PRODUCT_ID).strip()
    purchase_token = (purchase_token or "").strip()

    if package_name != DEFAULT_PACKAGE_NAME:
        return {"ok": False, "reason": "PACKAGE_NAME_MISMATCH"}

    if product_id != DEFAULT_PRODUCT_ID:
        return {"ok": False, "reason": "PRODUCT_ID_MISMATCH"}

    if not purchase_token:
        return {"ok": False, "reason": "EMPTY_PURCHASE_TOKEN"}

    try:
        service = _android_publisher_service()
        response = (
            service.purchases()
            .subscriptionsv2()
            .get(packageName=package_name, token=purchase_token)
            .execute()
        )
    except HttpError as e:
        return {"ok": False, "reason": "GOOGLE_HTTP_ERROR", "error": str(e)}
    except Exception as e:
        return {"ok": False, "reason": "GOOGLE_VERIFY_ERROR", "error": str(e)}

    state = str(response.get("subscriptionState") or "")
    line_items = response.get("lineItems") or []
    matching_items = [x for x in line_items if str(x.get("productId") or "") == product_id]

    if not matching_items:
        return {
            "ok": False,
            "reason": "PRODUCT_NOT_FOUND_IN_SUBSCRIPTION",
            "subscription_state": state,
            "raw": response,
        }

    expiry_dt = None
    for item in matching_items:
        candidate = _parse_google_time(item.get("expiryTime"))
        if candidate and (expiry_dt is None or candidate > expiry_dt):
            expiry_dt = candidate

    if expiry_dt is None:
        return {
            "ok": False,
            "reason": "MISSING_EXPIRY_TIME",
            "subscription_state": state,
            "raw": response,
        }

    now = datetime.now(timezone.utc)
    active = state in ACTIVE_STATES and expiry_dt > now

    order_id = (
        response.get("latestOrderId")
        or response.get("linkedPurchaseToken")
        or None
    )

    return {
        "ok": bool(active),
        "reason": "OK" if active else "SUBSCRIPTION_NOT_ACTIVE",
        "package_name": package_name,
        "product_id": product_id,
        "subscription_state": state,
        "expiry_time": _iso_utc(expiry_dt),
        "order_id": order_id,
        "raw": response,
    }
