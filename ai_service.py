import os
import json
from typing import Any, Dict, List, Optional

import requests


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_URL = "https://api.openai.com/v1/responses"

AI_MOCK = os.getenv("AI_MOCK", "0").strip().lower() in ("1", "true", "yes", "y")


def build_ai_input(
    locale: str,
    score: int,
    verdict: str,
    top3: List[Any],
    risks: List[Dict[str, Any]],
    text_sample: str,
    summary: str = "",
    contract_type: str = "",
    quick_decision: Optional[Dict[str, Any]] = None,
    next_steps: Optional[List[str]] = None,
    strengths: Optional[List[str]] = None,
    doc_locale: str = "",
    mode: str = "normal",
) -> str:
    payload = {
        "locale": locale,
        "doc_locale": doc_locale,
        "score": score,
        "verdict": verdict,
        "summary": summary,
        "contract_type": contract_type,
        "quick_decision": quick_decision or {},
        "top3": top3[:3],
        "risks_top": risks[:8],
        "next_steps": (next_steps or [])[:6],
        "strengths": (strengths or [])[:6],
        "text_sample": text_sample[:5000],
        "mode": mode,
    }
    return json.dumps(payload, ensure_ascii=False)


def _try_parse_input_json(data_json: str) -> Dict[str, Any]:
    try:
        return json.loads(data_json)
    except Exception:
        return {}


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _safe_list(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for item in v:
        s = _safe_str(item)
        if s:
            out.append(s)
    return out


def _mock_ai(locale: str, score: int = 50, verdict: str = "", risks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    risks = risks or []
    red_flags = [r.get("title", "") for r in risks[:3] if r.get("title")]

    if str(locale).lower().startswith("de"):
        return {
            "plain_summary": "Das Dokument enthält Klauseln, die für den Nutzer nachteilig sein können. Besonders wichtig sind Haftung, Gerichtsstand und Kündigungsbedingungen.",
            "what_it_means": "In der Praxis kann das bedeuten, dass die andere Partei stärkere Rechte hat, während dein Risiko oder deine Kosten steigen.",
            "negotiation_moves": [
                "Bitte um klarere Haftungsgrenzen.",
                "Verlange ausgewogene Kündigungsfristen.",
                "Prüfe, ob der Gerichtsstand für dich praktikabel ist.",
            ],
            "red_flags": red_flags if red_flags else [
                "Haftungsklausel",
                "Kündigungsfrist",
                "Gerichtsstand",
            ],
            "rewritten_clauses": [
                {
                    "title": "Haftung",
                    "before": "Unbegrenzte oder einseitige Haftung des Vertragspartners.",
                    "after": "Die Haftung ist auf typische, vorhersehbare Schäden und maximal auf die Vertragssumme begrenzt.",
                },
                {
                    "title": "Kündigung",
                    "before": "Unklare oder einseitig lange Kündigungsfrist.",
                    "after": "Beide Parteien können den Vertrag mit klar definierter Frist kündigen.",
                },
            ],
            "_mock": True,
        }

    if str(locale).lower().startswith("en"):
        return {
            "plain_summary": "This document contains clauses that may be unfavourable to the user. The most important risks concern liability, termination, and jurisdiction.",
            "what_it_means": "In practice, this may mean higher costs, a harder exit path, or a weaker negotiation position for you.",
            "negotiation_moves": [
                "Ask for clearer liability limits.",
                "Clarify termination terms and notice periods.",
                "Check whether the court venue favours only one side.",
            ],
            "red_flags": red_flags if red_flags else [
                "Liability",
                "Termination",
                "Jurisdiction",
            ],
            "rewritten_clauses": [
                {
                    "title": "Liability",
                    "before": "One side bears broad or unlimited liability risks.",
                    "after": "Liability should be limited to foreseeable damages and a reasonable contract value cap.",
                },
                {
                    "title": "Termination",
                    "before": "Termination rights are unclear or one-sided.",
                    "after": "Either party may terminate with a clearly defined notice period.",
                },
            ],
            "_mock": True,
        }

    return {
        "plain_summary": "Ta umowa zawiera zapisy, które mogą być dla użytkownika niekorzystne. Najważniejsze ryzyka dotyczą odpowiedzialności, wypowiedzenia i właściwości sądu.",
        "what_it_means": "W praktyce może to oznaczać większe koszty, trudniejsze zakończenie współpracy albo słabszą pozycję negocjacyjną po Twojej stronie.",
        "negotiation_moves": [
            "Poproś o limit odpowiedzialności.",
            "Doprecyzuj warunki i terminy wypowiedzenia.",
            "Sprawdź, czy właściwość sądu nie faworyzuje tylko jednej strony.",
        ],
        "red_flags": red_flags if red_flags else [
            "Odpowiedzialność",
            "Wypowiedzenie",
            "Właściwość sądu",
        ],
        "rewritten_clauses": [
            {
                "title": "Odpowiedzialność",
                "before": "Strona ponosi pełną odpowiedzialność za wszelkie szkody.",
                "after": "Odpowiedzialność strony ogranicza się do szkód przewidywalnych i do wysokości wynagrodzenia z umowy.",
            },
            {
                "title": "Wypowiedzenie",
                "before": "Umowa może być rozwiązana na warunkach niejasnych lub jednostronnych.",
                "after": "Każda ze stron może wypowiedzieć umowę z zachowaniem jasno określonego terminu.",
            },
        ],
        "_mock": True,
    }


def _extract_output_text(out: Dict[str, Any]) -> str:
    text = out.get("output_text", "") or ""
    if text:
        return text

    parts: List[str] = []
    for item in out.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", "") or "")
    return "".join(parts).strip()


def _parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def _normalize_ai_result(parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    plain_summary = _safe_str(parsed_json.get("plain_summary"))
    what_it_means = _safe_str(parsed_json.get("what_it_means"))
    negotiation_moves = _safe_list(parsed_json.get("negotiation_moves"))[:5]
    red_flags = _safe_list(parsed_json.get("red_flags"))[:5]

    rewritten_raw = parsed_json.get("rewritten_clauses")
    rewritten_clauses: List[Dict[str, str]] = []

    if isinstance(rewritten_raw, list):
        for item in rewritten_raw[:3]:
            if isinstance(item, dict):
                rewritten_clauses.append({
                    "title": _safe_str(item.get("title")),
                    "before": _safe_str(item.get("before")),
                    "after": _safe_str(item.get("after")),
                })

    return {
        "plain_summary": plain_summary,
        "what_it_means": what_it_means,
        "negotiation_moves": negotiation_moves,
        "red_flags": red_flags,
        "rewritten_clauses": rewritten_clauses,
        "_mock": False,
    }


def call_ai_explain(data_json: str, locale: str, mode: str = "normal") -> Dict[str, Any]:
    parsed = _try_parse_input_json(data_json)
    score = int(parsed.get("score", 50) or 50)
    verdict = str(parsed.get("verdict", "") or "")
    risks = parsed.get("risks_top", []) if isinstance(parsed.get("risks_top", []), list) else []
    mode = (mode or parsed.get("mode") or "normal").lower().strip()
    if mode not in {"normal", "simple"}:
        mode = "normal"

    if AI_MOCK:
        print("AI MOCK MODE: returning mock response")
        return _mock_ai(locale=locale, score=score, verdict=verdict, risks=risks)

    if not OPENAI_API_KEY:
        print("AI FALLBACK: missing OPENAI_API_KEY -> mock")
        return _mock_ai(locale=locale, score=score, verdict=verdict, risks=risks)

    system = (
        "You are SafeContract PRO, a practical contract advisor for non-lawyers. "
        "Your job is to explain contract risks in plain language, with real-world consequences and usable negotiation suggestions. "
        "Be specific, practical, and short. Avoid academic legal style. "
        "Return ONLY valid JSON without markdown. "
        "The JSON must contain: plain_summary, what_it_means, negotiation_moves, red_flags, rewritten_clauses."
    )

    if mode == "simple":
        system += " Use extra-simple language, like explaining the contract to a non-expert friend."

    lang = str(locale).lower()
    if lang.startswith("de"):
        user = (
            "Antworte auf Deutsch. "
            "Erkläre die Vertragsrisiken so, dass eine normale Person sie sofort versteht. "
            "Konzentriere dich auf echte Folgen im Alltag oder im Geschäft. "
            "Wenn eine Klausel einseitig ist, sage das klar. "
            "Gib kurze, direkt nutzbare Verhandlungsvorschläge. "
            "rewritten_clauses muss eine Liste von Objekten {title, before, after} sein. "
            "negotiation_moves und red_flags müssen Listen sein. "
            "plain_summary: 2-4 kurze Sätze. "
            "what_it_means: kurz und praktisch. "
            "Daten JSON:\n" + data_json
        )
    elif lang.startswith("en"):
        user = (
            "Reply in English. "
            "Explain the contract risks in a way a normal person can understand immediately. "
            "Focus on real-life consequences and practical negotiation moves. "
            "If a clause is one-sided, say so clearly. "
            "rewritten_clauses must be a list of objects {title, before, after}. "
            "negotiation_moves and red_flags must be lists. "
            "plain_summary: 2-4 short sentences. "
            "what_it_means: short and practical. "
            "Input JSON:\n" + data_json
        )
    else:
        user = (
            "Odpowiedz po polsku. "
            "Wyjaśnij ryzyka umowy tak, żeby normalna osoba zrozumiała je od razu. "
            "Skup się na praktycznych skutkach w życiu lub biznesie. "
            "Jeśli zapis jest jednostronny, napisz to wprost. "
            "Daj krótkie i konkretne propozycje negocjacji. "
            "rewritten_clauses ma być listą obiektów {title, before, after}. "
            "negotiation_moves i red_flags mają być listami. "
            "plain_summary: 2-4 krótkie zdania. "
            "what_it_means: krótko i praktycznie. "
            "Dane wejściowe JSON:\n" + data_json
        )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
    }

    try:
        r = requests.post(OPENAI_URL, headers=headers, json=body, timeout=60)
        if r.status_code >= 400:
            print(f"AI FALLBACK: OpenAI error {r.status_code} -> mock")
            print(r.text[:500])
            return _mock_ai(locale=locale, score=score, verdict=verdict, risks=risks)

        out = r.json()
        text = _extract_output_text(out)
        parsed_json = _parse_json_response(text)
        if parsed_json is None:
            print("AI FALLBACK: non-JSON response -> mock")
            return _mock_ai(locale=locale, score=score, verdict=verdict, risks=risks)

        normalized = _normalize_ai_result(parsed_json)
        if not normalized["plain_summary"] and not normalized["what_it_means"]:
            print("AI FALLBACK: empty useful content -> mock")
            return _mock_ai(locale=locale, score=score, verdict=verdict, risks=risks)

        return normalized

    except Exception as e:
        print("AI FALLBACK exception -> mock:", str(e))
        return _mock_ai(locale=locale, score=score, verdict=verdict, risks=risks)
