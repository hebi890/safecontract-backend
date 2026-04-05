from fastapi import APIRouter
from pydantic import BaseModel
import sqlite3

DB_PATH = "history.sqlite3"  # jeśli masz inną ścieżkę do DB, podmień tutaj

router = APIRouter(prefix="/dev", tags=["dev"])


class DeviceReq(BaseModel):
    device_id: str


@router.post("/reset_free")
def reset_free(req: DeviceReq):
    """
    DEV ONLY:
    Czyści historię analiz dla podanego device_id,
    więc licznik FREE wraca do 0/2 dla tego telefonu.
    """
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM history WHERE device_id = ?", (req.device_id,))
        deleted = cur.rowcount
        con.commit()
        return {
            "ok": True,
            "device_id": req.device_id,
            "deleted_rows": deleted,
            "free_used": 0,
        }
    finally:
        con.close()