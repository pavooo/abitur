import json
import zipfile
from pathlib import Path

import pymupdf
import pytest
from accounts.models import Lehrkraft
from archiv.models import Fach

from importer.schemas import SCHEMA_VERSION


def minimal_pdf_bytes(seiten: int = 1) -> bytes:
    """Erzeugt ein echtes, minimales PDF mit der angegebenen Seitenzahl –
    nötig, damit PyMuPDF beim Erzeugen der Vorschaubilder nicht scheitert."""
    dokument = pymupdf.open()
    for _ in range(seiten):
        dokument.new_page()
    daten = dokument.tobytes()
    dokument.close()
    return daten


def schreibe_paket_zip(
    ziel_pfad: Path,
    *,
    manifest: dict,
    klausuren: list[dict] | None = None,
    taxonomie: dict | None = None,
    pdf_seiten_je_klausur: dict | None = None,
    ohne_pdf: set | None = None,
) -> Path:
    klausuren = klausuren or []
    pdf_seiten_je_klausur = pdf_seiten_je_klausur or {}
    ohne_pdf = ohne_pdf or set()

    with zipfile.ZipFile(ziel_pfad, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        if taxonomie is not None:
            zf.writestr("taxonomie.json", json.dumps(taxonomie))
        for klausur_daten in klausuren:
            klausur_id = klausur_daten["id"]
            zf.writestr(f"klausuren/{klausur_id}.json", json.dumps(klausur_daten))
            if klausur_id not in ohne_pdf:
                seiten = pdf_seiten_je_klausur.get(klausur_id, 3)
                zf.writestr(f"dateien/{klausur_id}.pdf", minimal_pdf_bytes(seiten))
    return ziel_pfad


def manifest_fuer(fach_kuerzel: str, *, schema_version: str = SCHEMA_VERSION) -> dict:
    return {"schema_version": schema_version, "fach": fach_kuerzel, "erstellt_am": "2026-11-01"}


def klausur_json(
    *,
    id: str,  # noqa: A002
    fach: str,
    jahr: int = 2024,
    kursart: str = "LK",
    termin: str = "haupttermin",
    variante: str = "A",
    titel: str = "Analysis",
    themen: list[str] | None = None,
) -> dict:
    return {
        "id": id,
        "fach": fach,
        "jahr": jahr,
        "kursart": kursart,
        "termin": termin,
        "variante": variante,
        "titel": titel,
        "aufgaben": [
            {
                "nummer": 1,
                "kontext": "Bakterienwachstum",
                "seiten": [1, 2],
                "teilaufgaben": [
                    {
                        "bezeichnung": "1a",
                        "seite": 1,
                        "text": "Berechnen Sie den Anfangsbestand.",
                        "punkte": 4,
                        "themen": themen or [],
                        "anforderungsbereich": "I",
                        "operatoren": ["berechnen"],
                        "begruendung": "Einsetzen in die Modellgleichung.",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def fach_mathe(db):
    return Fach.objects.create(name="Mathematik", kuerzel="M")


@pytest.fixture
def admin_lehrkraft(db):
    return Lehrkraft.objects.create_user(
        email="admin@schule.de",
        password="s3hrGeheim!",
        status=Lehrkraft.Status.AKTIV,
        ist_admin=True,
    )
