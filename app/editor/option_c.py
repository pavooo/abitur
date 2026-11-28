"""Option C (CLAUDE.md, Abschnitt Lehrkraft-Editor): JSON aus einem eigenen, externen
KI-Werkzeug der Lehrkraft. Die App ruft dabei selbst keinen KI-Dienst auf – sie erzeugt
nur einen Prompt zum Kopieren und validiert/übernimmt das von der Lehrkraft eingefügte
Ergebnis. Validierung mit demselben Schema wie der Admin-Import (`schema/klausur.schema.json`),
nur dass `id` nicht gebraucht wird und Metadaten optional sind (sie kommen primär aus
Schritt 1; sind sie im JSON vorhanden, werden Abweichungen als Konflikt gemeldet).
"""

import copy
import dataclasses
import json

from archiv.models import Aufgabe, Teilaufgabe, Thema
from importer.schemas import KLAUSUR_SCHEMA, validiere_gegen_schema

BEISPIEL_JSON = {
    "fach": "M",
    "jahr": 2024,
    "kursart": "LK",
    "termin": "haupttermin",
    "variante": "A",
    "titel": "Analysis – Prüfungsteil B",
    "hilfsmittel": "TR",
    "aufgaben": [
        {
            "nummer": 1,
            "kontext": "Bakterienwachstum",
            "seiten": [2, 3],
            "pruefungsteil": "mit_hilfsmitteln",
            "aufgabenbereich": "pflicht",
            "teilaufgaben": [
                {
                    "bezeichnung": "1c",
                    "seite": 3,
                    "text": "Ermitteln Sie den Zeitpunkt, zu dem der Bestand am stärksten zunimmt.",
                    "punkte": 6,
                    "themen": ["analysis.diff.wendepunkt", "analysis.anwendung.wachstum"],
                    "anforderungsbereich": "II",
                    "operatoren": ["ermitteln"],
                    "begruendung": "Stärkste Zunahme = Maximum der 1. Ableitung = Wendestelle.",
                }
            ],
        }
    ],
}

_METADATEN_FELDER = [
    ("fach", "Fach"),
    ("jahr", "Jahr"),
    ("kursart", "Kursart"),
    ("termin", "Termin"),
    ("variante", "Variante"),
    ("titel", "Titel"),
    ("hilfsmittel", "Hilfsmittel"),
]


def _option_c_schema() -> dict:
    """Dieselben `$defs` wie beim Admin-Import, aber nur `aufgaben` ist Pflicht: `id`
    wird hier nicht gebraucht, die übrigen Metadaten sind optional (sie kommen aus
    Schritt 1) und dienen – falls vorhanden – nur dem Konflikt-Abgleich."""
    schema = copy.deepcopy(KLAUSUR_SCHEMA)
    schema["required"] = ["aufgaben"]
    schema["properties"].pop("id", None)
    return schema


OPTION_C_SCHEMA = _option_c_schema()


@dataclasses.dataclass
class OptionCErgebnis:
    fehler: list[str]
    konflikte: list[dict]
    daten: dict | None

    @property
    def gueltig(self) -> bool:
        return not self.fehler and self.daten is not None


def erzeuge_prompt(klausur) -> str:
    themen = Thema.objects.filter(fach=klausur.fach).order_by("kennung")
    themen_zeilen = "\n".join(
        f"- {thema.kennung}: {thema.name}"
        + (f" (Synonyme: {', '.join(thema.synonyme)})" if thema.synonyme else "")
        for thema in themen
    )
    beispiel = json.dumps(BEISPIEL_JSON, ensure_ascii=False, indent=2)

    return (
        "Du bekommst gleich eine Abiturklausur als PDF. Zerlege sie in Aufgaben und "
        "Teilaufgaben und gib AUSSCHLIESSLICH gültiges JSON im unten beschriebenen Format "
        "aus – ohne Markdown-Codeblock, ohne weitere Erklärungen.\n\n"
        "Metadaten dieser Klausur (bitte unverändert übernehmen, insbesondere den Termin):\n"
        f"- Fach: {klausur.fach.name} ({klausur.fach.kuerzel})\n"
        f"- Jahr: {klausur.jahr}\n"
        f"- Kursart: {klausur.kursart}\n"
        f"- Termin: {klausur.termin}\n"
        f"- Variante: {klausur.variante or '–'}\n"
        f"- Titel: {klausur.titel}\n"
        f"- Hilfsmittel: {klausur.hilfsmittel}\n\n"
        "Wähle Themen für jede Teilaufgabe NUR aus dieser Liste (Kennung: Name):\n"
        f"{themen_zeilen}\n\n"
        "Erwartetes JSON-Format (vollständiges Beispiel):\n"
        f"{beispiel}\n\n"
        "Gib ausschließlich dieses JSON aus, keinen weiteren Text."
    )


def _metadaten_konflikte(daten: dict, klausur) -> list[dict]:
    aktuelle_werte = {
        "fach": klausur.fach.kuerzel,
        "jahr": klausur.jahr,
        "kursart": klausur.kursart,
        "termin": klausur.termin,
        "variante": klausur.variante,
        "titel": klausur.titel,
        "hilfsmittel": klausur.hilfsmittel,
    }
    konflikte = []
    for feld, label in _METADATEN_FELDER:
        if feld not in daten:
            continue
        wert_json = daten[feld]
        wert_schritt1 = aktuelle_werte[feld]
        if wert_json != wert_schritt1:
            konflikte.append(
                {
                    "feld": feld,
                    "label": label,
                    "schritt1": wert_schritt1,
                    "json": wert_json,
                }
            )
    return konflikte


def validiere(roh_text: str, *, klausur) -> OptionCErgebnis:
    try:
        daten = json.loads(roh_text)
    except json.JSONDecodeError as exc:
        return OptionCErgebnis(fehler=[f"Kein gültiges JSON: {exc}"], konflikte=[], daten=None)

    schema_fehler = validiere_gegen_schema(daten, OPTION_C_SCHEMA)
    if schema_fehler:
        return OptionCErgebnis(fehler=schema_fehler, konflikte=[], daten=None)

    fehler = []
    themen_kennungen = set(
        Thema.objects.filter(fach=klausur.fach).values_list("kennung", flat=True)
    )
    for aufgabe in daten["aufgaben"]:
        seite_von, seite_bis = aufgabe["seiten"]
        if seite_von > seite_bis:
            fehler.append(
                f"Aufgabe {aufgabe['nummer']}: Seitenbereich {aufgabe['seiten']} ist ungültig."
            )

        bezeichnungen = [t["bezeichnung"] for t in aufgabe["teilaufgaben"]]
        if len(bezeichnungen) != len(set(bezeichnungen)):
            fehler.append(
                f"Aufgabe {aufgabe['nummer']}: Teilaufgaben-Bezeichnungen sind nicht eindeutig."
            )

        for teilaufgabe in aufgabe["teilaufgaben"]:
            for kennung in teilaufgabe.get("themen", []):
                if kennung not in themen_kennungen:
                    fehler.append(
                        f"Aufgabe {aufgabe['nummer']}, Teilaufgabe {teilaufgabe['bezeichnung']}: "
                        f"Thema {kennung!r} existiert nicht."
                    )

    nummern = [aufgabe["nummer"] for aufgabe in daten["aufgaben"]]
    if len(nummern) != len(set(nummern)):
        fehler.append("Aufgaben-Nummern sind nicht eindeutig.")

    if fehler:
        return OptionCErgebnis(fehler=fehler, konflikte=[], daten=None)

    konflikte = _metadaten_konflikte(daten, klausur)
    return OptionCErgebnis(fehler=[], konflikte=konflikte, daten=daten)


def uebernehmen(klausur, daten: dict) -> None:
    """Übernimmt Aufgaben/Teilaufgaben aus validierten Option-C-Daten in die Klausur.
    Bestehende Aufgaben/Teilaufgaben werden über Nummer bzw. Bezeichnung gematcht und
    aktualisiert statt ersetzt – anders als der Admin-Import (CLAUDE.md, Abschnitt
    Import-Regeln): hier kann an denselben Aufgaben/Teilaufgaben bereits manuell
    markierte Arbeit (Bereiche) existieren und soll erhalten bleiben. Nichts, was in
    `daten` fehlt, wird gelöscht."""
    for aufgabe_daten in daten["aufgaben"]:
        seite_von, seite_bis = aufgabe_daten["seiten"]
        aufgabe, _erstellt = Aufgabe.objects.update_or_create(
            klausur=klausur,
            nummer=aufgabe_daten["nummer"],
            defaults={
                "kontext": aufgabe_daten.get("kontext", ""),
                "pruefungsteil": aufgabe_daten["pruefungsteil"],
                "aufgabenbereich": aufgabe_daten.get(
                    "aufgabenbereich", Aufgabe.Aufgabenbereich.KEINE_ANGABE
                ),
                "seite_von": seite_von,
                "seite_bis": seite_bis,
            },
        )
        for teilaufgabe_daten in aufgabe_daten["teilaufgaben"]:
            teilaufgabe, _erstellt = Teilaufgabe.objects.update_or_create(
                aufgabe=aufgabe,
                bezeichnung=teilaufgabe_daten["bezeichnung"],
                defaults={
                    "text": teilaufgabe_daten["text"],
                    "seite": teilaufgabe_daten["seite"],
                    "punkte": teilaufgabe_daten.get("punkte"),
                    "anforderungsbereich": teilaufgabe_daten["anforderungsbereich"],
                    "operatoren": teilaufgabe_daten.get("operatoren", []),
                    "begruendung": teilaufgabe_daten.get("begruendung", ""),
                },
            )
            kennungen = teilaufgabe_daten.get("themen", [])
            if kennungen:
                themen = Thema.objects.filter(fach=klausur.fach, kennung__in=kennungen)
                teilaufgabe.themen.set(themen)
