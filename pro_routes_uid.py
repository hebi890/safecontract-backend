from fastapi import APIRouter, Depends

from auth_firebase import CurrentUser, get_current_user
from pro_user_db import get_pro_record, is_pro_user, set_pro_user, start_trial
from user_usage_db import get_free_used

router = APIRouter(prefix="/pro", tags=["pro"])

TESTER_EMAILS = {
    "darui890@gmail.com",
}


def is_tester_user(current_user: CurrentUser) -> bool:
    email = (getattr(current_user, "email", None) or "").strip().lower()
    return email in {e.strip().lower() for e in TESTER_EMAILS}


@router.get("/status")
def pro_status(current_user: CurrentUser = Depends(get_current_user)):
    tester = is_tester_user(current_user)
    record = get_pro_record(current_user.uid)
    is_pro = is_pro_user(current_user.uid) or tester
    used = get_free_used(current_user.uid)

    free_limit = 999999 if is_pro else 2
    free_left = max(free_limit - used, 0)

    return {
        "uid": current_user.uid,
        "email": getattr(current_user, "email", None),
        "is_pro": is_pro,
        "is_tester": tester,
        "is_trial_active": bool(record.get("trial_active")),
        "trial_until": record.get("trial_until"),
        "trial_started_at": record.get("trial_started_at"),
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


@router.post("/claim")
def pro_claim(current_user: CurrentUser = Depends(get_current_user)):
    set_pro_user(current_user.uid, source="dev_claim")
    return {"ok": True, "uid": current_user.uid, "is_pro": True}
