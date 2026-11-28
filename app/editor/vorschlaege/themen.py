"""Themen-Abgleich (CLAUDE.md, Abschnitt Regelbasierte Vorschläge): vergleicht einen
Text mit Themennamen und Synonymen der Taxonomie (Kleinschreibung, Umlaute
normalisiert, einfache Wortstamm-Toleranz) und liefert Treffer nach Relevanz sortiert.
Reine Funktion – `themen` kann echte `Thema`-Instanzen oder beliebige Objekte mit
`.pk`/`.kennung`/`.name`/`.synonyme` enthalten, was Tests ohne Datenbank erlaubt.
"""

import re

_UMLAUT_ERSATZ = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
_WORT_PATTERN = re.compile(r"[a-zäöüß]+", re.IGNORECASE)
_MIN_WORTLAENGE = 3
_WORTSTAMM_LAENGE = 5


def normalisiere(text: str) -> str:
    """Kleinschreibung + Umlaut-Normalisierung für robusten Textvergleich."""
    text = text.lower()
    for umlaut, ersatz in _UMLAUT_ERSATZ.items():
        text = text.replace(umlaut, ersatz)
    return text


def _wortstamm(wort: str) -> str:
    """Einfache Wortstamm-Toleranz: Die ersten Zeichen genügen für einen Treffer
    (z. B. teilen sich „Ableitung“ und „Ableitungsregel“ den Stamm „ablei“)."""
    return normalisiere(wort)[:_WORTSTAMM_LAENGE]


def _woerter(text: str) -> list[str]:
    return [wort for wort in _WORT_PATTERN.findall(text) if len(wort) >= _MIN_WORTLAENGE]


def schlage_themen_vor(text: str, themen, *, max_anzahl: int = 8) -> list[dict]:
    """Liefert die `max_anzahl` relevantesten Themen für `text`, absteigend sortiert.
    Relevanz = Summe der Längen der tatsächlich übereinstimmenden Wörter aus Name und
    Synonymen – längere (spezifischere) Treffer zählen mehr als kurze, generische."""
    text_staemme = {_wortstamm(wort) for wort in _woerter(text)}
    if not text_staemme:
        return []

    vorschlaege = []
    for thema in themen:
        suchwoerter = _woerter(thema.name)
        for synonym in thema.synonyme:
            suchwoerter.extend(_woerter(synonym))

        treffer = {wort for wort in suchwoerter if _wortstamm(wort) in text_staemme}
        if not treffer:
            continue

        vorschlaege.append(
            {
                "thema_id": thema.pk,
                "kennung": thema.kennung,
                "name": thema.name,
                "score": sum(len(wort) for wort in treffer),
            }
        )

    vorschlaege.sort(key=lambda eintrag: eintrag["score"], reverse=True)
    return vorschlaege[:max_anzahl]
