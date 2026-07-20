import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_firebase import CurrentUser, get_current_user, is_anonymous_uid
from google_play_verifier import DEFAULT_PACKAGE_NAME, DEFAULT_PRODUCT_ID, verify_google_play_subscription
from pro_user_db import (
    clear_paid_pro_if_expired,
    get_pro_record,
    get_uid_for_purchase_token,
    is_paid_pro_user,
    is_pro_user,
    set_google_subscription_user,
    set_pro_user,
    start_trial,
    transfer_google_subscription_user,
)
from user_usage_db import get_free_used

router = APIRouter(prefix="/pro", tags=["pro"])

# Production default: no hard-coded testers. If you need free tester access,
# set SAFE_CONTRACT_TESTER_EMAILS="email1@gmail.com,email2@gmail.com" in Railway.
TESTER_EMAILS = {
    e.strip().lower()
    for e in os.getenv("SAFE_CONTRACT_TESTER_EMAILS", "").split(",")
    if e.strip()
}

DEBUG_PRO_CLAIM_ENABLED = os.getenv("DEBUG_PRO_CLAIM_ENABLED", "false").lower() == "true"


class GooglePlayVerifyRequest(BaseModel):
    product_id: str
    purchase_token: str
    package_name: str = DEFAULT_PACKAGE_NAME


def is_tester_user(current_user: CurrentUser) -> bool:
    email = (getattr(current_user, "email", None) or "").strip().lower()
    return bool(email and email in TESTER_EMAILS)


def _refresh_google_subscription_if_possible(uid: str) -> None:
    record = get_pro_record(uid)
    token = (record.get("purchase_token") or "").strip()
    product_id = (record.get("product_id") or DEFAULT_PRODUCT_ID).strip()

    if not token:
        clear_paid_pro_if_expired(uid)
        return

    result = verify_google_play_subscription(
        package_name=DEFAULT_PACKAGE_NAME,
        product_id=product_id,
        purchase_token=token,
    )

    if result.get("ok"):
        set_google_subscription_user(
            uid,
            product_id=product_id,
            purchase_token=token,
            subscription_state=str(result.get("subscription_state") or ""),
            pro_until=str(result.get("expiry_time") or ""),
            order_id=result.get("order_id"),
            source="google_play_refresh",
        )
    else:
        clear_paid_pro_if_expired(uid)


@router.get("/status")
def pro_status(current_user: CurrentUser = Depends(get_current_user)):
    try:
        _refresh_google_subscription_if_possible(current_user.uid)
    except Exception as e:
        # Status should still work if Google API is temporarily unavailable.
        print("Google Play refresh skipped:", e)

    tester = is_tester_user(current_user)
    record = get_pro_record(current_user.uid)
    paid_pro = is_paid_pro_user(current_user.uid)
    is_pro = is_pro_user(current_user.uid) or tester
    used = get_free_used(current_user.uid)

    free_limit = 999999 if is_pro else 2
    free_left = max(free_limit - used, 0)

    return {
        "uid": current_user.uid,
        "email": getattr(current_user, "email", None),
        "is_pro": is_pro,
        "is_paid_pro": paid_pro,
        "is_tester": tester,
        "is_trial_active": bool(record.get("trial_active")),
        "trial_until": record.get("trial_until"),
        "trial_started_at": record.get("trial_started_at"),
        "pro_until": record.get("pro_until"),
        "subscription_state": record.get("subscription_state"),
        "product_id": record.get("product_id"),
        "free_limit": free_limit,
        "free_used": used,
        "free_left": free_left,
        "is_anonymous": current_user.is_anonymous,
    }


@router.post("/start_trial")
def pro_start_trial(current_user: CurrentUser = Depends(get_current_user)):
    result = start_trial(current_user.uid, days=3, source="manual_start_trial")
    return {
        "ok": True,
        "uid": current_user.uid,
        "started": bool(result.get("started")),
        "is_pro": bool(result.get("is_pro")),
        "is_trial_active": bool(result.get("trial_active")),
        "trial_until": result.get("trial_until"),
    }


@router.post("/google-play/verify")
def pro_google_play_verify(
    body: GooglePlayVerifyRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    if body.product_id != DEFAULT_PRODUCT_ID:
        raise HTTPException(status_code=400, detail="Invalid product_id")

    if body.package_name != DEFAULT_PACKAGE_NAME:
        raise HTTPException(status_code=400, detail="Invalid package_name")

    result = verify_google_play_subscription(
        package_name=body.package_name,
        product_id=body.product_id,
        purchase_token=body.purchase_token,
    )

    if not result.get("ok"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "GOOGLE_PLAY_SUBSCRIPTION_NOT_ACTIVE",
                "reason": result.get("reason"),
                "subscription_state": result.get("subscription_state"),
            },
        )

    token_owner = get_uid_for_purchase_token(body.purchase_token)
    transferred_from_anonymous = False

    if token_owner and token_owner != current_user.uid:
        can_transfer_from_guest = (
            not current_user.is_anonymous
            and is_anonymous_uid(token_owner)
        )
        if not can_transfer_from_guest:
            raise HTTPException(
                status_code=409,
                detail="Purchase token is already linked to another user",
            )

        try:
            transfer_google_subscription_user(
                token_owner,
                current_user.uid,
                product_id=body.product_id,
                purchase_token=body.purchase_token,
                subscription_state=str(result.get("subscription_state") or ""),
                pro_until=str(result.get("expiry_time") or ""),
                order_id=result.get("order_id"),
            )
        except ValueError:
            # The owner changed concurrently; fail closed instead of duplicating access.
            raise HTTPException(
                status_code=409,
                detail="Purchase token owner changed during transfer",
            )
        transferred_from_anonymous = True
    else:
        set_google_subscription_user(
            current_user.uid,
            product_id=body.product_id,
            purchase_token=body.purchase_token,
            subscription_state=str(result.get("subscription_state") or ""),
            pro_until=str(result.get("expiry_time") or ""),
            order_id=result.get("order_id"),
            source="google_play_verify",
        )

    return {
        "ok": True,
        "uid": current_user.uid,
        "is_pro": True,
        "is_paid_pro": True,
        "product_id": body.product_id,
        "pro_until": result.get("expiry_time"),
        "subscription_state": result.get("subscription_state"),
        "transferred_from_anonymous": transferred_from_anonymous,
    }


@router.post("/claim")
def pro_claim(current_user: CurrentUser = Depends(get_current_user)):
    if not DEBUG_PRO_CLAIM_ENABLED:
        raise HTTPException(
            status_code=410,
            detail="/pro/claim is disabled. Use /pro/google-play/verify.",
        )

    set_pro_user(current_user.uid, source="debug_claim")
    return {"ok": True, "uid": current_user.uid, "is_pro": True}
