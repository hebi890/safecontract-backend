from fastapi import APIRouter, Depends

from auth_firebase import CurrentUser, get_current_user
from pro_user_db import is_pro_user, set_pro_user

router = APIRouter(prefix="/pro", tags=["pro"])


@router.get("/status")
def pro_status(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "uid": current_user.uid,
        "is_pro": is_pro_user(current_user.uid),
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