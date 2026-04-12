from fastapi import APIRouter, Depends

from auth_firebase import CurrentUser, get_current_user
from pro_user_db import is_pro_user, set_pro_user
from user_usage_db import get_free_used

router = APIRouter(prefix="/pro", tags=["pro"])


@router.get("/status")
def pro_status(current_user: CurrentUser = Depends(get_current_user)):
    is_pro = is_pro_user(current_user.uid)
    used = get_free_used(current_user.uid)

    if is_pro:
        free_limit = 999999
    else:
        free_limit = 2

    free_left = max(free_limit - used, 0)

    return {
        "uid": current_user.uid,
        "is_pro": is_pro,
        "free_limit": free_limit,
        "free_used": used,
        "free_left": free_left,
        "is_anonymous": current_user.is_anonymous,
    }


@router.post("/claim")
def pro_claim(current_user: CurrentUser = Depends(get_current_user)):
    # DEV ONLY
    set_pro_user(current_user.uid, True)

    return {
        "ok": True,
        "uid": current_user.uid,
        "is_pro": True,
    }