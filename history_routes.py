from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from history_db import upsert_history, list_history, delete_history, update_pdf_path

router = APIRouter(prefix="/history", tags=["history"])


class HistoryIn(BaseModel):
    id: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    file_name: str = Field(..., min_length=1)

    summary: str = ""
    full_text: str = ""

    contract_type: Optional[str] = None
    pdf_path: Optional[str] = None
    risk: Literal["ok", "warning", "danger"] = "warning"

    model_config = ConfigDict(extra="ignore")


class PdfPathIn(BaseModel):
    device_id: str = Field(..., min_length=1)
    pdf_path: str = Field(..., min_length=1)

    model_config = ConfigDict(extra="ignore")


@router.post("/add")
def add_history(item: HistoryIn):
    upsert_history(item.model_dump())
    return {"ok": True}


@router.get("/list", response_model=List[HistoryIn])
def get_history(device_id: str, limit: int = 100):
    return list_history(device_id=device_id, limit=limit)


@router.delete("/{item_id}")
def del_history(item_id: str, device_id: str):
    ok = delete_history(device_id=device_id, item_id=item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.post("/{item_id}/pdf_path")
def set_pdf_path(item_id: str, body: PdfPathIn):
    ok = update_pdf_path(
        device_id=body.device_id,
        item_id=item_id,
        pdf_path=body.pdf_path,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
