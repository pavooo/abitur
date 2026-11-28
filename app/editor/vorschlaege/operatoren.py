"""Operatoren-Abgleich (CLAUDE.md, Abschnitt Regelbasierte Vorschläge): schlägt den
Anforderungsbereich einer Teilaufgabe anhand des darin vorkommenden Operators vor.
Reine Funktionen; `lade_operatoren` kapselt den einzigen Dateizugriff.
"""

import json
from pathlib import Path

from django.conf import settings


def lade_operatoren(fach_name: str) -> dict[str, str]:
    """Lädt die Operatorenliste eines Fachs (Operator -> typischer Anforderungsbereich)
    aus `schema/operatoren/<fach-name>.json` (Dateiname wie bei den Taxonomien: der
    kleingeschriebene Fach-Name, z. B. „mathematik“). Liefert ein leeres Dict, wenn für
    das Fach (noch) keine Liste existiert – fehlende Vorschläge sind kein Fehler."""
    dateiname = fach_name.lower().replace(" ", "_")
    pfad = Path(settings.REPO_ROOT) / "schema" / "operatoren" / f"{dateiname}.json"
    if not pfad.exists():
        return {}
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return {
        eintrag["operator"].lower(): eintrag["anforderungsbereich"]
        for eintrag in daten["operatoren"]
    }


def schlage_anforderungsbereich_vor(text: str, operatoren: dict[str, str]) -> dict | None:
    """Sucht den ersten im Text vorkommenden bekannten Operator (längere zuerst, damit
    z. B. „kritisch Stellung nehmen“ vor „Stellung nehmen“ erkannt wird) und gibt
    Operator + typischen Anforderungsbereich zurück, oder None ohne Treffer."""
    text_normalisiert = text.lower()
    for operator in sorted(operatoren, key=len, reverse=True):
        if operator in text_normalisiert:
            return {"operator": operator, "anforderungsbereich": operatoren[operator]}
    return None
