"""Vollständigkeitsprüfung vor dem Einreichen (CLAUDE.md, Abschnitt Lehrkraft-Editor,
Schritt 4 „Prüfen & Einreichen"): listet fehlende Pflichtangaben auf, die das Einreichen
blockieren, getrennt von bloßen Hinweisen (z. B. fehlende Themen), die nicht blockieren.
Die Pflichtangaben entsprechen genau dem, was `schema/klausur.schema.json` für den
Admin-Import verlangt – eine eingereichte Klausur muss sich später identisch importieren
lassen können.
"""

import dataclasses


@dataclasses.dataclass
class Vollstaendigkeitspruefung:
    pflicht_luecken: list[str]
    hinweise: list[str]

    @property
    def ist_vollstaendig(self) -> bool:
        return not self.pflicht_luecken


def pruefe(klausur) -> Vollstaendigkeitspruefung:
    pflicht_luecken = []
    hinweise = []

    if not klausur.pdf:
        pflicht_luecken.append("Kein Klausur-PDF hochgeladen.")

    aufgaben = list(
        klausur.aufgaben.prefetch_related(
            "bereiche", "teilaufgaben__themen", "teilaufgaben__bereiche"
        ).order_by("nummer")
    )
    if not aufgaben:
        pflicht_luecken.append("Noch keine Aufgaben angelegt.")

    for aufgabe in aufgaben:
        bezeichnung = f"Aufgabe {aufgabe.nummer}"
        # Bewusst `bereiche.exists()`, nicht `seite_von is None`: Option C setzt
        # `seite_von`/`seite_bis` direkt aus dem JSON, ohne einen Bereich anzulegen
        # (CLAUDE.md, Abschnitt Option C) – das muss hier weiterhin als Lücke gelten.
        if not aufgabe.bereiche.exists():
            pflicht_luecken.append(f"{bezeichnung}: kein Bereich markiert.")

        teilaufgaben = list(aufgabe.teilaufgaben.all())
        if not teilaufgaben:
            pflicht_luecken.append(f"{bezeichnung}: keine Teilaufgaben angelegt.")

        for teilaufgabe in teilaufgaben:
            ta_bezeichnung = f"{bezeichnung}, Teilaufgabe {teilaufgabe.bezeichnung}"
            if not teilaufgabe.bereiche.exists():
                pflicht_luecken.append(f"{ta_bezeichnung}: kein Bereich markiert.")
            if not teilaufgabe.text.strip():
                pflicht_luecken.append(f"{ta_bezeichnung}: kein Text.")
            if not teilaufgabe.anforderungsbereich:
                pflicht_luecken.append(f"{ta_bezeichnung}: kein Anforderungsbereich.")
            if not teilaufgabe.themen.exists():
                hinweise.append(f"{ta_bezeichnung}: kein Thema zugeordnet.")

    return Vollstaendigkeitspruefung(pflicht_luecken=pflicht_luecken, hinweise=hinweise)
