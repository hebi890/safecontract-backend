from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from pro_db import is_pro_device
from ai_service import build_ai_input, call_ai_explain

router = APIRouter(prefix="/ai", tags=["ai"])


class AiExplainIn(BaseModel):
    device_id: str
    locale: str
    score: int
    verdict: str
    top3: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []
    text_sample: str = ""


@router.post("/explain")
def ai_explain(body: AiExplainIn):
    # PRO-only
    if not is_pro_device(body.device_id):
        raise HTTPException(status_code=403, detail="PRO_REQUIRED")

    data_json = build_ai_input(
        locale=body.locale,
        score=body.score,
        verdict=body.verdict,
        top3=body.top3,
        risks=body.risks,
        text_sample=body.text_sample,
    )

    try:
        ai = call_ai_explain(data_json=data_json, locale=body.locale)
        return {"ok": True, "ai": ai}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI_ERROR: {str(e)}")