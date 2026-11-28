"""Teilaufgaben-Mustererkennung (CLAUDE.md, Abschnitt Regelbasierte Vorschläge):
erkennt Muster wie „a)“, „1.2“ oder „(6 Punkte)“ in einem Fließtext und schlägt eine
Aufteilung in Teilaufgaben vor. Reine Funktion, kein Django-Bezug.
"""

import re

_MARKER_PATTERN = re.compile(r"(?m)^\s*(?P<bezeichnung>[a-z]\)|\d+\.\d+)\s+")
_PUNKTE_PATTERN = re.compile(r"\(\s*(\d+)\s*(?:Punkte?|P\.?)\s*\)", re.IGNORECASE)


def erkenne_teilaufgaben(text: str) -> list[dict]:
    """Schlägt eine Aufteilung in Teilaufgaben vor. Jeder Eintrag enthält
    `bezeichnung` (z. B. „a“ oder „1.2“), `text` (der Abschnitt bis zum nächsten
    Marker) und `punkte` (aus einer Klammerangabe wie „(6 Punkte)“, sonst None). Wird
    kein Marker gefunden, ist das Ergebnis leer – dann legt die Lehrkraft Teilaufgaben
    manuell an."""
    treffer = list(_MARKER_PATTERN.finditer(text))

    vorschlaege = []
    for index, markierung in enumerate(treffer):
        start = markierung.end()
        ende = treffer[index + 1].start() if index + 1 < len(treffer) else len(text)
        segment_text = text[start:ende].strip()
        if not segment_text:
            continue

        bezeichnung = markierung.group("bezeichnung").rstrip(")")
        punkte_treffer = _PUNKTE_PATTERN.search(segment_text)
        punkte = int(punkte_treffer.group(1)) if punkte_treffer else None

        vorschlaege.append({"bezeichnung": bezeichnung, "text": segment_text, "punkte": punkte})

    return vorschlaege
