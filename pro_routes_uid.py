from fastapi import APIRouter, Depends

from auth_firebase import CurrentUser, get_current_user
from pro_user_db import is_pro_user, set_pro_user

router = APIRouter(prefix="/pro", tags=["pro"])


@router.get("/status")
def pro_status(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "ok": True,
        "uid": current_user.uid,
        "is_pro": is_pro_user(current_user.uid),
    }


@router.post("/sync")
def pro_sync(current_user: CurrentUser = Depends(get_current_user)):
    # Minimum viable flow:
    # after successful purchase / restore in the app, call this endpoint.
    # Later you can harden this with real Play/App Store receipt validation.
    set_pro_user(current_user.uid, source="client_sync")
    return {
        "ok": True,
        "uid": current_user.uid,
        "is_pro": True,
    }
