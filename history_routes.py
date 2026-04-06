from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from auth_firebase import CurrentUser, get_current_user
from history_db import (
    upsert_history,
    list_history,
    delete_history,
    update_pdf_path,
)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/list")
def history_list(
    limit: int = 100,
    current_user: CurrentUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return list_history(current_user.uid, limit)


@router.post("/add")
def history_add(
    payload: Dict[str, Any],
    current_user: CurrentUser = Depends(get_current_user),
):
    payload["uid"] = current_user.uid
    upsert_history(payload)
    return {"ok": True}


@router.delete("/{item_id}")
def history_delete(
    item_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    ok = delete_history(current_user.uid, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.post("/{item_id}/pdf_path")
def history_set_pdf(
    item_id: str,
    payload: Dict[str, Any],
    current_user: CurrentUser = Depends(get_current_user),
):
    pdf_path = payload.get("pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=400, detail="Missing pdf_path")

    ok = update_pdf_path(current_user.uid, item_id, pdf_path)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")

    return {"ok": True}