from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pro_db import set_pro_device, is_pro_device
from pro_dev import is_dev_pro

router = APIRouter(prefix="/pro", tags=["pro"])


class ProClaimIn(BaseModel):
    device_id: str
    code: str


@router.get("/status")
def pro_status(device_id: str):
    is_pro = is_pro_device(device_id) or is_dev_pro(device_id)
    return {
        "device_id": device_id,
        "is_pro": is_pro,
    }


@router.post("/claim")
def pro_claim(data: ProClaimIn):
    VALID_CODE = "TESTPRO123"

    if data.code != VALID_CODE:
        raise HTTPException(status_code=403, detail="Invalid code")

    set_pro_device(data.device_id, True)

    return {
        "ok": True,
        "device_id": data.device_id,
        "is_pro": True,
    }