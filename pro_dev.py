from fastapi import APIRouter
from pydantic import BaseModel
import json
from pathlib import Path

router = APIRouter(prefix="/dev", tags=["dev"])

DB_FILE = Path("dev_pro.json")


def load_db():
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text(encoding="utf-8"))
        except:
            return {}
    return {}


def save_db(data):
    DB_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


class DevProIn(BaseModel):
    device_id: str


@router.post("/pro_on")
def pro_on(payload: DevProIn):
    db = load_db()
    db[payload.device_id] = True
    save_db(db)

    print(f"DEV PRO ON -> {payload.device_id}")

    return {"ok": True, "device_id": payload.device_id, "is_pro": True}


@router.post("/pro_off")
def pro_off(payload: DevProIn):
    db = load_db()
    db[payload.device_id] = False
    save_db(db)

    print(f"DEV PRO OFF -> {payload.device_id}")

    return {"ok": True, "device_id": payload.device_id, "is_pro": False}


def is_dev_pro(device_id: str) -> bool:
    db = load_db()
    return db.get(device_id, False)