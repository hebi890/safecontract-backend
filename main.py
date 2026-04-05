import os
import re
import json
import uuid
import shutil
import hashlib
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("OPENAI_API_KEY present:", bool(OPENAI_API_KEY))

from history_db import init_db, count_history
from ai_service import build_ai_input, call_ai_explain

from pro_db import init_pro_db, is_pro_device
from pro_routes import router as pro_router
from pro_dev import router as dev_router, is_dev_pro
from history_routes import router as history_router

import PyPDF2
from docx import Document
from pdf2image import convert_from_path
import pytesseract
from pytesseract import Output


print("🔥 MAIN FILE LOADED FROM:", __file__)

FREE_LIMIT = 2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

AI_CACHE_PATH = os.path.join(BASE_DIR, "ai_cache.json")

POPPLER_PATH = r"C:\poppler\Library\bin"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

app = FastAPI(title="SafeContract API")

init_db()
init_pro_db()

app.include_router(pro_router)
app.include_router(dev_router)
app.include_router(history_router)

print("✅ history_router loaded")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_LANGS = {"pl", "de", "en"}


CATEGORY_LABELS = {
    "liability": {
        "pl": "Odpowiedzialność",
        "de": "Haftung",
        "en": "Liability",
    },
    "penalties": {
        "pl": "Kary i opłaty",
        "de": "Strafen und Gebühren",
        "en": "Penalties and fees",
    },
    "renewal": {
        "pl": "Przedłużenie",
        "de": "Verlängerung",
        "en": "Renewal",
    },
    "unilateral_changes": {
        "pl": "Jednostronne zmiany",
        "de": "Einseitige Änderungen",
        "en": "Unilateral changes",
    },
    "jurisdiction": {
        "pl": "Sąd i jurysdykcja",
        "de": "Gerichtsstand und Recht",
        "en": "Court and jurisdiction",
    },
    "payment": {
        "pl": "Płatności",
        "de": "Zahlungen",
        "en": "Payments",
    },
    "general": {
        "pl": "Ogólne",
        "de": "Allgemein",
        "en": "General",
    },
}


def t(lang: str, pl: str, de: str, en: str) -> str:
    return {"pl": pl, "de": de, "en": en}.get(lang, en)


def make_ai_cache_key(text: str, doc_locale: str, result_lang: str, mode: str) -> str:
    payload = f"{doc_locale}|{result_lang}|{mode}|{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_ai_cache() -> Dict[str, Any]:
    try:
        if not os.path.exists(AI_CACHE_PATH):
            return {}
        with open(AI_CACHE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
        return {}
    except Exception as e:
        print("AI CACHE LOAD ERROR:", e)
        return {}


def _save_ai_cache(cache: Dict[str, Any]) -> None:
    try:
        tmp = AI_CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp, AI_CACHE_PATH)
    except Exception as e:
        print("AI CACHE SAVE ERROR:", e)


def find_cached_ai(cache_key: str) -> Optional[Dict[str, Any]]:
    cache = _load_ai_cache()
    item = cache.get(cache_key)
    if isinstance(item, dict):
        print("AI CACHE HIT:", cache_key[:12])
        return item
    print("AI CACHE MISS:", cache_key[:12])
    return None


def store_cached_ai(cache_key: str, payload: Dict[str, Any]) -> None:
    cache = _load_ai_cache()
    cache[cache_key] = payload
    _save_ai_cache(cache)


def choose_doc_locale(text: str) -> str:
    txt = (text or "").lower()

    de_hits = [
        " agb", "kündigung", "haftung", "gerichtsstand", "widerruf",
        "vertragsstrafe", "zahlungsfrist", "rechnung", "schadensersatz",
        "laufzeit", "verlängerung", "fristlos", "allgemeine geschäftsbedingungen"
    ]
    en_hits = [
        "terms and conditions", "liability", "termination", "jurisdiction",
        "penalty", "governing law", "automatic renewal"
    ]
    pl_hits = [
        "regulamin", "odpowiedzialność", "wypowiedzenie", "kara umowna",
        "jurysdykcja", "sąd właściwy", "automatyczne przedłużenie"
    ]

    de_score = sum(1 for x in de_hits if x in txt)
    en_score = sum(1 for x in en_hits if x in txt)
    pl_score = sum(1 for x in pl_hits if x in txt)

    if de_score >= en_score and de_score >= pl_score and de_score > 0:
        return "de"
    if en_score >= pl_score and en_score > 0:
        return "en"
    return "pl"


def _read_pdf_text(path: str) -> str:
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += "\n" + (page.extract_text() or "")
    except Exception:
        pass
    return text.strip()


def _read_docx_text(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs).strip()


def _ocr_pdf(path: str) -> Dict[str, Any]:
    result = {
        "text": "",
        "used_ocr": False,
        "ocr_avg_conf": None,
        "extract_method": "text",
    }

    if not os.path.exists(TESSERACT_CMD):
        return result

    try:
        images = convert_from_path(
            path,
            poppler_path=POPPLER_PATH if os.path.exists(POPPLER_PATH) else None,
        )
        page_texts: List[str] = []
        confs: List[float] = []

        for img in images:
            data = pytesseract.image_to_data(img, output_type=Output.DICT, lang="deu+eng")
            words = []
            for i, raw in enumerate(data.get("text", [])):
                token = (raw or "").strip()
                if token:
                    words.append(token)
                try:
                    conf = float(data.get("conf", [])[i])
                    if conf >= 0:
                        confs.append(conf)
                except Exception:
                    pass
            page_texts.append(" ".join(words))

        text = "\n".join(page_texts).strip()
        if text:
            result["text"] = text
            result["used_ocr"] = True
            result["extract_method"] = "ocr"
            if confs:
                result["ocr_avg_conf"] = round(sum(confs) / len(confs), 2)
    except Exception:
        pass

    return result


def _extract_text(path: str) -> Dict[str, Any]:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        text = _read_pdf_text(path)
        if text:
            return {
                "text": text,
                "used_ocr": False,
                "ocr_avg_conf": None,
                "extract_method": "pdf_text",
            }

        ocr = _ocr_pdf(path)
        if ocr["text"]:
            return ocr

        return {
            "text": "",
            "used_ocr": False,
            "ocr_avg_conf": None,
            "extract_method": "pdf_text_empty",
        }

    if ext == ".docx":
        return {
            "text": _read_docx_text(path),
            "used_ocr": False,
            "ocr_avg_conf": None,
            "extract_method": "docx_text",
        }

    raise HTTPException(status_code=400, detail="Unsupported file")


def find_snippet(text: str, patterns: List[str], radius: int = 110) -> Optional[str]:
    source = text or ""
    for pattern in patterns:
        match = re.search(pattern, source, re.IGNORECASE)
        if match:
            start = max(0, match.start() - radius)
            end = min(len(source), match.end() + radius)
            snippet = source[start:end].strip()
            snippet = re.sub(r"\s+", " ", snippet)
            return snippet[:280]
    return None


def category_label(category: str, result_lang: str) -> str:
    labels = CATEGORY_LABELS.get(category) or CATEGORY_LABELS["general"]
    return labels.get(result_lang, labels["en"])


def normalize_level(level: Any) -> str:
    value = str(level or "medium").strip().lower()
    if value in {"low", "medium", "high"}:
        return value
    if value in {"warn", "warning", "mid", "moderate"}:
        return "medium"
    return "medium"


def build_quick_decision(score: int, result_lang: str) -> Dict[str, str]:
    if score <= 30:
        return {
            "label": t(result_lang, "Raczej bezpieczne", "Eher sicher", "Mostly safe"),
            "reason": t(
                result_lang,
                "Nie wykryto poważnych czerwonych flag w szybkim skanie, ale nadal przeczytaj dokument przed podpisaniem.",
                "Im schnellen Scan wurden keine schweren roten Flaggen erkannt, aber lies das Dokument trotzdem vor der Unterschrift.",
                "No major red flags were found in the quick scan, but you should still read the document before signing.",
            ),
        }
    if score <= 69:
        return {
            "label": t(result_lang, "Podpisz ostrożnie", "Vorsichtig unterschreiben", "Sign with caution"),
            "reason": t(
                result_lang,
                "Są zapisy wymagające uwagi. Przed podpisaniem sprawdź odpowiedzialność, koszty i warunki zakończenia umowy.",
                "Einige Klauseln erfordern Aufmerksamkeit. Prüfe vor der Unterschrift Haftung, Kosten und Kündigungsbedingungen.",
                "Some clauses need attention. Before signing, check liability, costs, and termination terms.",
            ),
        }
    return {
        "label": t(result_lang, "Nie podpisuj bez sprawdzenia", "Nicht ohne Prüfung unterschreiben", "Do not sign without review"),
        "reason": t(
            result_lang,
            "Wykryto istotne ryzyka. Warto wyjaśnić lub negocjować kluczowe klauzule przed podpisaniem.",
            "Es wurden wesentliche Risiken erkannt. Wichtige Klauseln sollten vor der Unterschrift geklärt oder verhandelt werden.",
            "Significant risks were found. Key clauses should be clarified or negotiated before signing.",
        ),
    }


def add_risk(
    risks: List[Dict[str, Any]],
    score_breakdown: List[Dict[str, Any]],
    *,
    result_lang: str,
    level: str,
    category: str,
    title_pl: str,
    title_de: str,
    title_en: str,
    plain_pl: str,
    plain_de: str,
    plain_en: str,
    why_pl: str,
    why_de: str,
    why_en: str,
    rec_pl: str,
    rec_de: str,
    rec_en: str,
    patterns: List[str],
    text: str,
    weight: int,
):
    evidence = find_snippet(text, patterns)
    if not evidence:
        return

    title = t(result_lang, title_pl, title_de, title_en)
    risk = {
        "id": str(uuid.uuid4()),
        "level": normalize_level(level),
        "title": title,
        "category": category,
        "weight": int(weight),
        "evidence": evidence,
        "plain_explanation": t(result_lang, plain_pl, plain_de, plain_en),
        "why_it_matters": t(result_lang, why_pl, why_de, why_en),
        "recommendation": t(result_lang, rec_pl, rec_de, rec_en),
        "clause_hint": category_label(category, result_lang),
    }
    risks.append(risk)

    score_breakdown.append({
        "key": category,
        "label": category_label(category, result_lang),
        "impact": int(weight),
    })


def compute_verdict(score: int, result_lang: str) -> str:
    if score <= 30:
        return t(result_lang, "Niskie ryzyko", "Niedriges Risiko", "Low risk")
    if score <= 69:
        return t(result_lang, "Średnie ryzyko", "Mittleres Risiko", "Medium risk")
    return t(result_lang, "Wysokie ryzyko", "Hohes Risiko", "High risk")


def classify_contract_type(text: str, doc_locale: str, result_lang: str) -> str:
    txt = (text or "").lower()

    if any(x in txt for x in ["agb", "allgemeine geschäftsbedingungen", "terms and conditions", "regulamin"]):
        return t(result_lang, "regulamin / AGB", "AGB / Bedingungen", "terms and conditions")
    if any(x in txt for x in ["umowa zlecenie", "dienstvertrag", "service agreement"]):
        return t(result_lang, "umowa usługowa", "Dienstleistungsvertrag", "service agreement")
    if any(x in txt for x in ["najem", "miete", "lease"]):
        return t(result_lang, "umowa najmu", "Mietvertrag", "lease agreement")

    return t(result_lang, "umowa ogólna", "allgemeiner Vertrag", "general contract")


def build_summary(score: int, risk_count: int, contract_type: str, result_lang: str) -> str:
    if risk_count == 0:
        return t(
            result_lang,
            f"Nie wykryto oczywistych czerwonych flag w szybkim skanie heurystycznym. Dokument wygląda jak: {contract_type}. Mimo to warto przeczytać całość przed podpisaniem.",
            f"Im heuristischen Schnellscan wurden keine offensichtlichen roten Flaggen erkannt. Das Dokument wirkt wie: {contract_type}. Vor der Unterschrift sollte der Vertrag dennoch vollständig geprüft werden.",
            f"No obvious red flags were found in the quick heuristic scan. The document appears to be: {contract_type}. It should still be reviewed before signing.",
        )

    return t(
        result_lang,
        f"Wykryto {risk_count} potencjalne ryzyka. Największą uwagę zwróć na odpowiedzialność, wypowiedzenie i jednostronne zmiany warunków. Typ dokumentu: {contract_type}.",
        f"Es wurden {risk_count} potenzielle Risiken erkannt. Achte besonders auf Haftung, Kündigung und einseitige Änderungen der Bedingungen. Dokumenttyp: {contract_type}.",
        f"{risk_count} potential risks were detected. Pay special attention to liability, termination, and unilateral changes of terms. Document type: {contract_type}.",
    )


def analyze_contract_advanced(text: str, doc_locale: str, result_lang: str) -> Dict[str, Any]:
    risks: List[Dict[str, Any]] = []
    score_breakdown: List[Dict[str, Any]] = []
    strengths: List[str] = []
    next_steps: List[str] = []
    missing_clauses: List[str] = []

    contract_type = classify_contract_type(text, doc_locale, result_lang)

    add_risk(
        risks, score_breakdown,
        result_lang=result_lang,
        level="high",
        category="liability",
        title_pl="Ograniczenie odpowiedzialności",
        title_de="Haftungsbeschränkung",
        title_en="Liability limitation",
        plain_pl="Druga strona ogranicza swoją odpowiedzialność za szkody lub błędy.",
        plain_de="Die andere Partei beschränkt ihre Haftung für Schäden oder Fehler.",
        plain_en="The other party limits its liability for damages or mistakes.",
        why_pl="To może utrudnić dochodzenie odszkodowania lub roszczeń, gdy usługa nie zostanie wykonana prawidłowo.",
        why_de="Das kann es schwieriger machen, Schadensersatz oder Ansprüche durchzusetzen, wenn die Leistung mangelhaft ist.",
        why_en="This may make it harder to claim compensation if the service is faulty or not delivered properly.",
        rec_pl="Sprawdź wyjątki dotyczące rażącego niedbalstwa, winy umyślnej i szkód osobowych. Poproś o doprecyzowanie odpowiedzialności.",
        rec_de="Prüfe Ausnahmen für grobe Fahrlässigkeit, Vorsatz und Personenschäden. Bitte um eine klarere Haftungsregelung.",
        rec_en="Check the exceptions for gross negligence, intent, and personal injury. Ask for clearer liability wording.",
        patterns=[r"\bhaftung\b", r"liability", r"odpowiedzialno(?:ść|sci|ści)"],
        text=text,
        weight=20,
    )

    add_risk(
        risks, score_breakdown,
        result_lang=result_lang,
        level="high",
        category="penalties",
        title_pl="Kary umowne lub dodatkowe opłaty",
        title_de="Vertragsstrafe oder Zusatzgebühren",
        title_en="Contractual penalties or extra fees",
        plain_pl="Umowa przewiduje dodatkowe opłaty lub kary przy naruszeniu warunków.",
        plain_de="Der Vertrag sieht zusätzliche Gebühren oder Strafen bei Verstößen vor.",
        plain_en="The contract includes extra fees or penalties for breaches.",
        why_pl="Takie zapisy mogą znacząco podnieść koszty w razie opóźnienia, błędu albo wcześniejszego zakończenia współpracy.",
        why_de="Solche Klauseln können die Kosten bei Verspätung, Fehlern oder vorzeitiger Beendigung stark erhöhen.",
        why_en="These clauses can significantly increase costs in case of delay, breach, or early termination.",
        rec_pl="Sprawdź, kiedy kara się nalicza, czy jest limit i czy wysokość opłat jest proporcjonalna.",
        rec_de="Prüfe, wann die Strafe fällig wird, ob es eine Obergrenze gibt und ob die Gebühren verhältnismäßig sind.",
        rec_en="Check when the penalty applies, whether there is a cap, and whether the fees are proportionate.",
        patterns=[r"vertragsstrafe", r"kara umowna", r"penalt(?:y|ies)", r"zusatzgeb[uü]hr", r"additional fee"],
        text=text,
        weight=18,
    )

    add_risk(
        risks, score_breakdown,
        result_lang=result_lang,
        level="medium",
        category="renewal",
        title_pl="Automatyczne przedłużenie",
        title_de="Automatische Verlängerung",
        title_en="Automatic renewal",
        plain_pl="Umowa może odnowić się sama, jeśli nie wypowiesz jej na czas.",
        plain_de="Der Vertrag kann sich automatisch verlängern, wenn du nicht rechtzeitig kündigst.",
        plain_en="The contract may renew automatically if you do not cancel in time.",
        why_pl="Możesz nieświadomie wejść w kolejny okres umowy i ponosić dalsze koszty.",
        why_de="Du könntest unbemerkt in eine neue Vertragsperiode rutschen und weitere Kosten tragen.",
        why_en="You may unintentionally enter another contract period and keep paying.",
        rec_pl="Sprawdź termin wypowiedzenia i ustaw przypomnienie przed końcem umowy.",
        rec_de="Prüfe die Kündigungsfrist und setze dir eine Erinnerung vor Vertragsende.",
        rec_en="Check the notice period and set a reminder well before the contract end date.",
        patterns=[r"automatisch(?:e|en)? verl[aä]nger", r"automatyczn\w+ przedłuż", r"automatic(?:ally)? renew"],
        text=text,
        weight=14,
    )

    add_risk(
        risks, score_breakdown,
        result_lang=result_lang,
        level="medium",
        category="unilateral_changes",
        title_pl="Jednostronna zmiana warunków",
        title_de="Einseitige Änderung der Bedingungen",
        title_en="Unilateral change of terms",
        plain_pl="Druga strona zastrzega sobie prawo do samodzielnej zmiany warunków.",
        plain_de="Die andere Partei behält sich vor, Bedingungen einseitig zu ändern.",
        plain_en="The other party reserves the right to change terms unilaterally.",
        why_pl="To może oznaczać zmianę ceny, zasad lub zakresu usługi bez realnej negocjacji z Twojej strony.",
        why_de="Das kann bedeuten, dass Preis, Regeln oder Leistungsumfang ohne echte Verhandlung geändert werden.",
        why_en="This may allow prices, rules, or service scope to change without real negotiation.",
        rec_pl="Sprawdź, kiedy zmiany są dopuszczalne i czy masz prawo wypowiedzieć umowę po zmianie.",
        rec_de="Prüfe, wann Änderungen zulässig sind und ob du danach kündigen darfst.",
        rec_en="Check when changes are allowed and whether you can terminate after the change.",
        patterns=[r"beh[aä]lt sich vor", r"einseitig", r"jednostronn\w+ zmian", r"we reserve the right", r"may change these terms"],
        text=text,
        weight=15,
    )

    add_risk(
        risks, score_breakdown,
        result_lang=result_lang,
        level="medium",
        category="jurisdiction",
        title_pl="Niekorzystny sąd lub jurysdykcja",
        title_de="Ungünstiger Gerichtsstand oder Rechtswahl",
        title_en="Unfavourable court venue or jurisdiction",
        plain_pl="Spór może być rozpatrywany w miejscu niewygodnym albo kosztownym dla Ciebie.",
        plain_de="Ein Streitfall könnte an einem für dich ungünstigen oder teuren Ort geführt werden.",
        plain_en="A dispute may have to be resolved in a venue that is inconvenient or costly for you.",
        why_pl="To może utrudnić dochodzenie swoich praw i zwiększyć koszt ewentualnego sporu.",
        why_de="Das kann die Durchsetzung deiner Rechte erschweren und die Kosten eines Rechtsstreits erhöhen.",
        why_en="This may make enforcing your rights harder and more expensive.",
        rec_pl="Sprawdź właściwość sądu i prawo właściwe. W umowach konsumenckich taki zapis bywa ograniczony przepisami.",
        rec_de="Prüfe Gerichtsstand und anwendbares Recht. Bei Verbraucherverträgen sind solche Klauseln oft begrenzt.",
        rec_en="Check the venue and governing law. In consumer contracts, such clauses may be limited by law.",
        patterns=[r"gerichtsstand", r"court of competent jurisdiction", r"jurysdykcj", r"sąd właściwy", r"governing law"],
        text=text,
        weight=12,
    )

    add_risk(
        risks, score_breakdown,
        result_lang=result_lang,
        level="medium",
        category="payment",
        title_pl="Krótki termin płatności lub jednostronne obowiązki",
        title_de="Kurze Zahlungsfrist oder einseitige Pflichten",
        title_en="Short payment deadline or one-sided obligations",
        plain_pl="Bardzo krótki termin zapłaty albo nierówne obowiązki mogą działać na Twoją niekorzyść.",
        plain_de="Eine sehr kurze Zahlungsfrist oder einseitige Pflichten können zu deinem Nachteil wirken.",
        plain_en="A very short payment deadline or one-sided obligations may work against you.",
        why_pl="Może to prowadzić do odsetek, blokad, dodatkowych kosztów albo łatwiejszego uznania Cię za stronę naruszającą umowę.",
        why_de="Das kann zu Zinsen, Sperren, Zusatzkosten oder einem schnelleren Vertragsverstoß auf deiner Seite führen.",
        why_en="This can lead to interest, suspension, extra fees, or quicker default on your side.",
        rec_pl="Sprawdź terminy płatności, odsetki i konsekwencje opóźnienia. Upewnij się, że obowiązki stron są proporcjonalne.",
        rec_de="Prüfe Zahlungsfristen, Zinsen und die Folgen eines Verzugs. Achte darauf, dass die Pflichten beider Seiten ausgewogen sind.",
        rec_en="Check payment deadlines, interest, and the consequences of late payment. Make sure obligations are balanced.",
        patterns=[r"zahlungsfrist", r"payment within \d+ days", r"płatn(?:ość|osci|ości)", r"rechnung ist sofort f[aä]llig"],
        text=text,
        weight=10,
    )

    txt = (text or "").lower()
    if any(x in txt for x in ["widerruf", "cancellation right", "prawo odstąpienia"]):
        strengths.append(
            t(
                result_lang,
                "Dokument zawiera ślady zapisów o odstąpieniu lub rezygnacji, co może ułatwić wyjście z umowy.",
                "Das Dokument enthält Hinweise auf Widerruf oder Rücktritt, was den Ausstieg aus dem Vertrag erleichtern kann.",
                "The document appears to include cancellation language, which may make exiting the contract easier.",
            )
        )

    if any(x in txt for x in ["kündigungsfrist", "notice period", "okres wypowiedzenia"]):
        strengths.append(
            t(
                result_lang,
                "W dokumencie widać odniesienia do okresu wypowiedzenia, co może poprawiać przewidywalność zakończenia umowy.",
                "Im Dokument gibt es Hinweise auf Kündigungsfristen, was die Beendigung berechenbarer machen kann.",
                "The document includes notice-period language, which can make termination more predictable.",
            )
        )

    if not any(x in txt for x in ["widerruf", "cancellation", "odstąpienia"]):
        missing_clauses.append(
            t(
                result_lang,
                "Brak jasnych śladów prawa odstąpienia lub rezygnacji.",
                "Keine klaren Hinweise auf Widerrufs- oder Rücktrittsrechte gefunden.",
                "No clear sign of cancellation or withdrawal rights was found.",
            )
        )

    if not any(x in txt for x in ["kündigungsfrist", "notice period", "okres wypowiedzenia"]):
        missing_clauses.append(
            t(
                result_lang,
                "Brak jasnego terminu wypowiedzenia.",
                "Keine klare Kündigungsfrist gefunden.",
                "No clear notice period was found.",
            )
        )

    total_risk = sum(abs(int(x.get("impact", 0))) for x in score_breakdown)
    score = max(0, min(100, total_risk))
    verdict = compute_verdict(score, result_lang)

    if risks:
        next_steps = [
            t(result_lang, "Przeczytaj dokładnie klauzule wskazane jako ryzyka.", "Lies die markierten Risikoklauseln sorgfältig.", "Read the clauses flagged as risks carefully."),
            t(result_lang, "Przed podpisaniem poproś o zmianę lub doprecyzowanie niekorzystnych zapisów.", "Bitte vor der Unterschrift um Änderungen oder Klarstellungen bei ungünstigen Klauseln.", "Ask for changes or clarifications to unfavourable clauses before signing."),
            t(result_lang, "Jeśli to umowa o większej wartości albo z długim okresem obowiązywania, rozważ konsultację z prawnikiem.", "Bei einem Vertrag mit höherem Wert oder längerer Laufzeit erwäge eine rechtliche Prüfung.", "If the contract has significant value or long duration, consider a legal review."),
        ]
    else:
        next_steps = [
            t(result_lang, "Przejrzyj dokument ręcznie przed podpisaniem.", "Prüfe das Dokument vor der Unterschrift nochmals manuell.", "Review the document manually before signing."),
            t(result_lang, "Zwróć uwagę na terminy, płatności i wypowiedzenie.", "Achte besonders auf Fristen, Zahlungen und Kündigung.", "Pay attention to deadlines, payments, and termination."),
        ]

    summary = build_summary(score, len(risks), contract_type, result_lang)

    return {
        "score": score,
        "verdict": verdict,
        "summary": summary,
        "contract_type": contract_type,
        "score_breakdown": score_breakdown,
        "strengths": strengths,
        "positives": strengths,
        "next_steps": next_steps,
        "missing_clauses": missing_clauses,
        "risks": risks,
    }


def infer_risk_level(score: int) -> str:
    if score <= 30:
        return "low"
    if score <= 69:
        return "medium"
    return "high"


def fallback_summary_simple(summary: str, result_lang: str) -> str:
    summary = str(summary or "").strip()
    if summary:
        return summary[:220]
    return t(
        result_lang,
        "Szybki skan nie wykrył jeszcze pełnego kontekstu. Przed podpisaniem sprawdź kluczowe klauzule.",
        "Der Schnellscan zeigt noch nicht den ganzen Kontext. Prüfe vor der Unterschrift die wichtigsten Klauseln.",
        "The quick scan does not show the full context yet. Review the key clauses before signing.",
    )


def _safe_string_list(value: Any, limit: int = 5) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        s = str(item or "").strip()
        if s:
            out.append(s)
    return out[:limit]


def render_ai_explanation_text(ai_data: Dict[str, Any], result_lang: str) -> str:
    parts: List[str] = []

    plain_summary = str(ai_data.get("plain_summary") or ai_data.get("summary_simple") or "").strip()
    what_it_means = str(ai_data.get("what_it_means") or "").strip()
    red_flags = _safe_string_list(ai_data.get("red_flags"), limit=3)
    negotiation = _safe_string_list(ai_data.get("negotiation_moves") or ai_data.get("negotiation_points"), limit=3)

    if plain_summary:
        parts.append(plain_summary)

    if what_it_means:
        parts.append(
            t(
                result_lang,
                f"Co to oznacza: {what_it_means}",
                f"Was das bedeutet: {what_it_means}",
                f"What this means: {what_it_means}",
            )
        )

    if red_flags:
        prefix = t(result_lang, "Największe czerwone flagi", "Wichtigste Red Flags", "Top red flags")
        parts.append(prefix + ": " + "; ".join(red_flags))

    if negotiation:
        prefix = t(result_lang, "Do negocjacji", "Zur Verhandlung", "To negotiate")
        parts.append(prefix + ": " + "; ".join(negotiation))

    return "\n\n".join([p for p in parts if p]).strip()


def normalize_ai_payload(ai_data: Optional[Dict[str, Any]], analysis: Dict[str, Any], result_lang: str) -> Dict[str, Any]:
    score = int(analysis.get("score", 0) or 0)
    quick_decision = analysis.get("quick_decision") or build_quick_decision(score, result_lang)

    if not isinstance(ai_data, dict):
        ai_data = {}

    plain_summary = str(ai_data.get("plain_summary") or ai_data.get("summary_simple") or "").strip()
    if not plain_summary:
        plain_summary = fallback_summary_simple(analysis.get("summary", ""), result_lang)

    red_flags = _safe_string_list(ai_data.get("red_flags"), limit=5)
    if not red_flags:
        red_flags = [str(x).strip() for x in (analysis.get("top3") or []) if str(x).strip()][:5]

    negotiation_points = _safe_string_list(
        ai_data.get("negotiation_moves") or ai_data.get("negotiation_points"),
        limit=5,
    )
    if not negotiation_points:
        negotiation_points = []
        for risk in (analysis.get("risks") or [])[:5]:
            rec = str((risk or {}).get("recommendation") or "").strip()
            if rec:
                negotiation_points.append(rec)
        negotiation_points = negotiation_points[:5]

    ai_text = render_ai_explanation_text({
        "plain_summary": plain_summary,
        "what_it_means": ai_data.get("what_it_means"),
        "red_flags": red_flags,
        "negotiation_moves": negotiation_points,
    }, result_lang)

    return {
        "summary_simple": plain_summary,
        "red_flags": red_flags,
        "negotiation_points": negotiation_points,
        "risk_level": infer_risk_level(score),
        "ai_explanation": ai_text,
        "quick_decision": {
            "label": str((quick_decision or {}).get("label") or ""),
            "reason": str((quick_decision or {}).get("reason") or ""),
            "confidence": max(55, min(95, 100 - score // 2)),
        },
    }


def normalize_analysis(raw: Dict[str, Any], result_lang: str) -> Dict[str, Any]:
    score = int(raw.get("score", 0) or 0)
    score = max(0, min(100, score))

    raw_risks = raw.get("risks") or []
    normalized_risks: List[Dict[str, Any]] = []
    for idx, risk in enumerate(raw_risks):
        category = str(risk.get("category") or "general")
        title = str(risk.get("title") or category_label(category, result_lang) or f"Risk {idx + 1}")
        normalized_risks.append({
            "id": str(risk.get("id") or uuid.uuid4()),
            "title": title,
            "level": normalize_level(risk.get("level")),
            "weight": int(risk.get("weight", 0) or 0),
            "category": category,
            "evidence": str(risk.get("evidence") or ""),
            "plain_explanation": str(risk.get("plain_explanation") or risk.get("why_it_matters") or ""),
            "why_it_matters": str(risk.get("why_it_matters") or ""),
            "recommendation": str(risk.get("recommendation") or ""),
            "clause_hint": str(risk.get("clause_hint") or category_label(category, result_lang)),
        })

    strengths = [str(x) for x in (raw.get("strengths") or raw.get("positives") or []) if str(x).strip()]
    next_steps = [str(x) for x in (raw.get("next_steps") or []) if str(x).strip()]
    missing_clauses = [str(x) for x in (raw.get("missing_clauses") or []) if str(x).strip()]

    summary = str(raw.get("summary") or "")
    contract_type = str(raw.get("contract_type") or t(result_lang, "umowa ogólna", "allgemeiner Vertrag", "general contract"))
    score_breakdown = raw.get("score_breakdown") or []

    if not score_breakdown and normalized_risks:
        score_breakdown = [
            {
                "key": r["category"],
                "label": category_label(r["category"], result_lang),
                "impact": int(r["weight"]),
            }
            for r in normalized_risks
        ]

    quick_decision = raw.get("quick_decision")
    if not isinstance(quick_decision, dict):
        quick_decision = build_quick_decision(score, result_lang)

    base = {
        "score": score,
        "verdict": str(raw.get("verdict") or compute_verdict(score, result_lang)),
        "summary": summary,
        "summary_simple": fallback_summary_simple(summary, result_lang),
        "risk_level": infer_risk_level(score),
        "locale": result_lang,
        "contract_type": contract_type,
        "document_type_confidence": float(raw.get("document_type_confidence", 0.6) or 0.6),
        "quick_decision": {
            "label": str(quick_decision.get("label") or build_quick_decision(score, result_lang)["label"]),
            "reason": str(quick_decision.get("reason") or build_quick_decision(score, result_lang)["reason"]),
            "confidence": max(55, min(95, 100 - score // 2)),
        },
        "score_breakdown": score_breakdown,
        "top3": [r["title"] for r in normalized_risks[:3]],
        "risks": normalized_risks,
        "strengths": strengths,
        "positives": strengths,
        "missing_clauses": missing_clauses,
        "next_steps": next_steps,
        "red_flags": [r["title"] for r in normalized_risks[:5]],
        "negotiation_points": [r["recommendation"] for r in normalized_risks[:5] if str(r.get("recommendation") or "").strip()][:5],
        "ai_explanation": str(raw.get("ai_explanation") or ""),
        "analysis_version": "v3_ai_cache_soft",
    }
    return base


def try_build_ai_input(text: str, analysis: Dict[str, Any], doc_locale: str, result_lang: str) -> str:
    try:
        return build_ai_input(
            locale=result_lang,
            score=int(analysis.get("score", 0) or 0),
            verdict=str(analysis.get("verdict") or ""),
            top3=analysis.get("top3") or [],
            risks=analysis.get("risks") or [],
            text_sample=text[:4000],
            summary=str(analysis.get("summary") or ""),
            contract_type=str(analysis.get("contract_type") or ""),
            quick_decision=analysis.get("quick_decision") or {},
            next_steps=analysis.get("next_steps") or [],
            strengths=analysis.get("strengths") or [],
            doc_locale=doc_locale,
            mode=result_lang,  # backwards-compatible if ai_service ignores extras through TypeError fallback below
        )
    except TypeError:
        return json.dumps({
            "locale": result_lang,
            "doc_locale": doc_locale,
            "score": int(analysis.get("score", 0) or 0),
            "verdict": str(analysis.get("verdict") or ""),
            "summary": str(analysis.get("summary") or ""),
            "contract_type": str(analysis.get("contract_type") or ""),
            "quick_decision": analysis.get("quick_decision") or {},
            "top3": analysis.get("top3") or [],
            "risks_top": (analysis.get("risks") or [])[:8],
            "next_steps": analysis.get("next_steps") or [],
            "strengths": analysis.get("strengths") or [],
            "text_sample": text[:4000],
        }, ensure_ascii=False)


def generate_ai_explanation(
    text: str,
    analysis: Dict[str, Any],
    doc_locale: str,
    result_lang: str,
    mode: str = "normal",
) -> Optional[Dict[str, Any]]:
    try:
        payload = try_build_ai_input(text=text, analysis=analysis, doc_locale=doc_locale, result_lang=result_lang)
        result = call_ai_explain(payload, result_lang, mode=mode)

        if isinstance(result, dict):
            return normalize_ai_payload(result, analysis, result_lang)

        if isinstance(result, str) and result.strip():
            return normalize_ai_payload(
                {
                    "plain_summary": result.strip(),
                    "what_it_means": "",
                    "negotiation_moves": [],
                    "red_flags": analysis.get("top3") or [],
                },
                analysis,
                result_lang,
            )
    except Exception as e:
        print("AI explanation failed:", e)

    return normalize_ai_payload(None, analysis, result_lang)


@app.post("/documents/upload")
async def upload_document(
    device_id: str = Form(...),
    file: UploadFile = File(...),
    ai: str = Form("false"),
    result_lang: str = Form("en"),
    mode: str = Form("normal"),
):
    result_lang = (result_lang or "en").lower()
    if result_lang not in SUPPORTED_LANGS:
        result_lang = "en"

    mode = (mode or "normal").lower().strip()
    if mode not in {"normal", "simple"}:
        mode = "normal"

    dev_pro = is_dev_pro(device_id)
    pro = is_pro_device(device_id) or dev_pro
    used = count_history(device_id)

    print(f"DEBUG pro={pro} dev_pro={dev_pro} device_id={device_id} used={used} limit={FREE_LIMIT}")

    if not pro and used >= FREE_LIMIT:
        raise HTTPException(status_code=403, detail="FREE_LIMIT_EXCEEDED")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Only .pdf and .docx are allowed.")

    name = f"{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, name)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    extraction = _extract_text(path)
    text = extraction["text"] or ""

    if not text.strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": "NO_TEXT_EXTRACTED",
                "message": "Could not extract readable text from file",
                "filename": file.filename,
                "extract_method": extraction.get("extract_method"),
                "used_ocr": extraction.get("used_ocr"),
            },
        )

    doc_locale = choose_doc_locale(text)
    analysis_raw = analyze_contract_advanced(text, doc_locale, result_lang)
    analysis = normalize_analysis(analysis_raw, result_lang)

    wants_ai = str(ai).lower() == "true"

    if pro and wants_ai:
        cache_key = make_ai_cache_key(text=text, doc_locale=doc_locale, result_lang=result_lang, mode=mode)
        ai_payload = find_cached_ai(cache_key)

        if ai_payload is None:
            ai_payload = generate_ai_explanation(
                text=text,
                analysis=analysis,
                doc_locale=doc_locale,
                result_lang=result_lang,
                mode=mode,
            )
            if isinstance(ai_payload, dict):
                store_cached_ai(cache_key, ai_payload)

        if isinstance(ai_payload, dict):
            analysis.update({
                "summary_simple": ai_payload.get("summary_simple", analysis.get("summary_simple", "")),
                "red_flags": ai_payload.get("red_flags", analysis.get("red_flags", [])),
                "negotiation_points": ai_payload.get("negotiation_points", analysis.get("negotiation_points", [])),
                "risk_level": ai_payload.get("risk_level", analysis.get("risk_level", infer_risk_level(int(analysis.get("score", 0) or 0)))),
                "quick_decision": ai_payload.get("quick_decision", analysis.get("quick_decision", {})),
                "ai_explanation": ai_payload.get("ai_explanation", ""),
            })

    response = {
        "analysis_id": str(uuid.uuid4()),
        "filename": name,
        "original_filename": file.filename,
        "is_pro": pro,
        "doc_locale": doc_locale,
        "result_lang": result_lang,
        "analysis_mode": mode,
        "used_ocr": extraction["used_ocr"],
        "extract_method": extraction["extract_method"],
        "ocr_avg_conf": extraction["ocr_avg_conf"],
        "text_len": len(text),
        "text_sample": text[:3000],
        "ai_enabled": pro and wants_ai,
        "ai_explanation": analysis.get("ai_explanation", ""),
        **analysis,
    }

    return response


@app.get("/health")
def health():
    return {"ok": True, "analysis_version": "v3_ai_cache_soft"}
