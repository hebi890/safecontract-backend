from typing import Dict, Any, List

TRANSLATIONS = {
    'pl': {
        'title_agb': 'Dokument wygląda na AGB (DE)',
        'hint_agb': 'AGB w Niemczech podlegają kontroli (AGB-Kontrolle).',
        'evidence_agb': "Występuje słowo 'AGB'.",
        'reco_agb': 'Sprawdź: Haftung, Kündigung, Gerichtsstand, Vertragsstrafe, jednostronne zmiany.',
        'title_haftung': 'Ograniczenie odpowiedzialności (Haftung)',
        'hint_haftung': 'W DE (BGB) wyłączenia odpowiedzialności są ograniczone, szczególnie w AGB.',
        'evidence_haftung': "Występuje 'Haftung/Haftungsausschluss'.",
        'reco_haftung': 'Zweryfikuj zgodność (np. brak wyłączeń dla Vorsatz/grobe Fahrlässigkeit).',
        'title_kundigung': 'Wypowiedzenie (Kündigung/Kündigungsfrist)',
        'hint_kundigung': 'Terminy wypowiedzenia i automatyczne przedłużenia są kluczowe.',
        'evidence_kundigung': "Występuje 'Kündigung/Kündigungsfrist'.",
        'reco_kundigung': 'Ustal jasną Kündigungsfrist i warunki przedłużeń.',
        'title_gericht': 'Właściwość sądu (Gerichtsstand)',
        'hint_gericht': 'Może być niekorzystna (koszty/odległość).',
        'evidence_gericht': "Występuje 'Gerichtsstand'.",
        'reco_gericht': 'Sprawdź czy jurysdykcja nie jest jednostronna.',
        'title_kara': 'Kara umowna',
        'hint_kara': 'Sprawdź wysokość, limit i przesłanki.',
        'evidence_kara': 'Wykryto frazę „kara umowna”.',
        'reco_kara': 'Dodaj limit (np. max % umowy) i precyzyjne warunki.',
        'title_zakaz': 'Zakaz konkurencji',
        'hint_zakaz': 'Uważaj na czas, terytorium i kary.',
        'evidence_zakaz': 'Wykryto zapis o zakazie konkurencji.',
        'reco_zakaz': 'Zawęź zakres + rozważ wynagrodzenie.',
        'title_short': 'Za mało tekstu do analizy',
        'hint_short': 'To może być skan albo słaby OCR.',
        'reco_short': 'Daj lepszy skan (300 DPI) lub PDF tekstowy.',
        'verdict_low': 'Niskie ryzyko (raczej OK, sprawdź szczegóły)',
        'verdict_mid': 'Średnie ryzyko (warto negocjować kilka punktów)',
        'verdict_high': 'Wysokie ryzyko (uważaj — rozważ konsultację prawną)',
        'summary': 'Wykryto {count} potencjalnych problemów.',
    },
    'de': {
        'title_agb': 'Dokument wirkt wie AGB (DE)',
        'hint_agb': 'AGB in Deutschland unterliegen der AGB-Kontrolle.',
        'evidence_agb': "Das Wort 'AGB' wurde gefunden.",
        'reco_agb': 'Prüfe: Haftung, Kündigung, Gerichtsstand, Vertragsstrafe und einseitige Änderungen.',
        'title_haftung': 'Haftungsbeschränkung',
        'hint_haftung': 'Nach deutschem Recht sind Haftungsausschlüsse, besonders in AGB, eingeschränkt.',
        'evidence_haftung': "'Haftung/Haftungsausschluss' wurde gefunden.",
        'reco_haftung': 'Prüfe die Wirksamkeit, z. B. keine Ausschlüsse für Vorsatz/grobe Fahrlässigkeit.',
        'title_kundigung': 'Kündigung / Kündigungsfrist',
        'hint_kundigung': 'Kündigungsfristen und automatische Verlängerungen sind entscheidend.',
        'evidence_kundigung': "'Kündigung/Kündigungsfrist' wurde gefunden.",
        'reco_kundigung': 'Lege klare Kündigungsfristen und Verlängerungsregeln fest.',
        'title_gericht': 'Gerichtsstand',
        'hint_gericht': 'Kann nachteilig sein (Kosten/Entfernung).',
        'evidence_gericht': "'Gerichtsstand' wurde gefunden.",
        'reco_gericht': 'Prüfe, ob die Zuständigkeit nicht einseitig festgelegt ist.',
        'title_kara': 'Vertragsstrafe',
        'hint_kara': 'Prüfe Höhe, Obergrenze und Voraussetzungen.',
        'evidence_kara': 'Die Formulierung „kara umowna” wurde gefunden.',
        'reco_kara': 'Ergänze eine Obergrenze und präzise Voraussetzungen.',
        'title_zakaz': 'Wettbewerbsverbot',
        'hint_zakaz': 'Achte auf Dauer, Gebiet und Sanktionen.',
        'evidence_zakaz': 'Ein Wettbewerbsverbot wurde erkannt.',
        'reco_zakaz': 'Grenze den Umfang ein und prüfe eine Vergütung.',
        'title_short': 'Zu wenig Text für die Analyse',
        'hint_short': 'Das kann ein Scan oder schwaches OCR sein.',
        'reco_short': 'Lade einen besseren Scan (300 DPI) oder ein Text-PDF hoch.',
        'verdict_low': 'Niedriges Risiko',
        'verdict_mid': 'Mittleres Risiko',
        'verdict_high': 'Hohes Risiko',
        'summary': 'Es wurden {count} potenzielle Probleme erkannt.',
    },
    'en': {
        'title_agb': 'Document appears to be German T&C / AGB',
        'hint_agb': 'German AGB are subject to fairness control.',
        'evidence_agb': "The word 'AGB' was detected.",
        'reco_agb': 'Review: liability, termination, venue, penalty clauses and unilateral changes.',
        'title_haftung': 'Liability limitation',
        'hint_haftung': 'Under German law, liability exclusions are restricted, especially in AGB.',
        'evidence_haftung': "'Haftung/Haftungsausschluss' was detected.",
        'reco_haftung': 'Check enforceability, e.g. no exclusions for intent/gross negligence.',
        'title_kundigung': 'Termination / notice period',
        'hint_kundigung': 'Notice periods and automatic renewals are key.',
        'evidence_kundigung': "'Kündigung/Kündigungsfrist' was detected.",
        'reco_kundigung': 'Set clear notice periods and renewal rules.',
        'title_gericht': 'Choice of court / venue',
        'hint_gericht': 'This may be unfavorable due to cost or distance.',
        'evidence_gericht': "'Gerichtsstand' was detected.",
        'reco_gericht': 'Check whether jurisdiction is not one-sided.',
        'title_kara': 'Contractual penalty',
        'hint_kara': 'Check the amount, cap and trigger conditions.',
        'evidence_kara': 'The phrase “kara umowna” was detected.',
        'reco_kara': 'Add a cap and precise trigger conditions.',
        'title_zakaz': 'Non-compete clause',
        'hint_zakaz': 'Watch the duration, geography and penalties.',
        'evidence_zakaz': 'A non-compete provision was detected.',
        'reco_zakaz': 'Narrow the scope and consider compensation.',
        'title_short': 'Too little text for analysis',
        'hint_short': 'This may be a scan or weak OCR.',
        'reco_short': 'Upload a better scan (300 DPI) or a text PDF.',
        'verdict_low': 'Low risk',
        'verdict_mid': 'Medium risk',
        'verdict_high': 'High risk',
        'summary': '{count} potential issues were detected.',
    },
}


def analyze_text_i18n(text: str, doc_locale: str = 'pl', result_locale: str = 'en') -> Dict[str, Any]:
    out_lang = result_locale if result_locale in ('pl', 'de', 'en') else 'en'
    tr = TRANSLATIONS[out_lang]
    risks: List[Dict[str, Any]] = []
    score = 100
    t = (text or '').lower()
    source_lang = 'de' if doc_locale == 'de' else 'pl'

    def add(level: str, weight: int, title: str, hint: str, evidence: str, recommendation: str) -> None:
        nonlocal score
        risks.append({
            'level': level,
            'weight': weight,
            'title': title,
            'hint': hint,
            'evidence': evidence,
            'recommendation': recommendation,
        })
        score -= int(weight)

    if source_lang == 'de':
        if 'agb' in t:
            add('medium', 15, tr['title_agb'], tr['hint_agb'], tr['evidence_agb'], tr['reco_agb'])
        if 'haftung' in t or 'haftungsausschluss' in t:
            add('high', 20, tr['title_haftung'], tr['hint_haftung'], tr['evidence_haftung'], tr['reco_haftung'])
        if 'kündigung' in t or 'kundigung' in t or 'kündigungsfrist' in t or 'kundigungsfrist' in t:
            add('medium', 10, tr['title_kundigung'], tr['hint_kundigung'], tr['evidence_kundigung'], tr['reco_kundigung'])
        if 'gerichtsstand' in t:
            add('medium', 10, tr['title_gericht'], tr['hint_gericht'], tr['evidence_gericht'], tr['reco_gericht'])

    if source_lang == 'pl':
        if 'kara umowna' in t:
            add('high', 25, tr['title_kara'], tr['hint_kara'], tr['evidence_kara'], tr['reco_kara'])
        if 'zakaz konkurencji' in t:
            add('high', 22, tr['title_zakaz'], tr['hint_zakaz'], tr['evidence_zakaz'], tr['reco_zakaz'])

    if len(text or '') < 300:
        add('low', 8, tr['title_short'], tr['hint_short'], f'{len(text or "")} chars detected.', tr['reco_short'])

    score = max(0, min(100, score))
    risks_sorted = sorted(risks, key=lambda x: x['weight'], reverse=True)
    if score >= 80:
        verdict = tr['verdict_low']
    elif score >= 50:
        verdict = tr['verdict_mid']
    else:
        verdict = tr['verdict_high']

    summary = tr['summary'].replace('{count}', str(len(risks_sorted)))
    top3 = [{'level': r['level'], 'title': r['title']} for r in risks_sorted[:3]]

    return {
        'score': score,
        'verdict': verdict,
        'summary': summary,
        'locale': out_lang,
        'contract_type': 'auto',
        'top3': top3,
        'risks': risks_sorted,
    }
