import dataclasses
import json
import zipfile
from pathlib import Path

from .schemas import (
    KLAUSUR_SCHEMA,
    MANIFEST_SCHEMA,
    SCHEMA_VERSION,
    TAXONOMIE_SCHEMA,
    validiere_gegen_schema,
)


class PaketFehler(Exception):
    """Das Paket als Ganzes ist nicht verarbeitbar (z. B. defektes ZIP, fehlende manifest.json)."""


@dataclasses.dataclass
class KlausurEintrag:
    id: str
    daten: dict
    pdf_pfad: Path | None
    ewh_pdf_pfad: Path | None
    schema_fehler: list[str]


@dataclasses.dataclass
class EntpacktesPaket:
    verzeichnis: Path
    manifest: dict
    taxonomie: dict | None
    klausuren: list[KlausurEintrag]


def entpacken(zip_pfad: Path, ziel_verzeichnis: Path) -> EntpacktesPaket:
    try:
        with zipfile.ZipFile(zip_pfad) as zf:
            _sicher_entpacken(zf, ziel_verzeichnis)
    except zipfile.BadZipFile as exc:
        raise PaketFehler("Die Datei ist kein gültiges ZIP-Archiv.") from exc

    manifest_pfad = ziel_verzeichnis / "manifest.json"
    if not manifest_pfad.exists():
        raise PaketFehler("Das Paket enthält keine manifest.json.")
    manifest = _json_laden(manifest_pfad, "manifest.json")

    manifest_fehler = validiere_gegen_schema(manifest, MANIFEST_SCHEMA)
    if manifest_fehler:
        raise PaketFehler("manifest.json ist ungültig: " + "; ".join(manifest_fehler))
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise PaketFehler(
            f"Nicht unterstützte Schema-Version {manifest['schema_version']!r} "
            f"(erwartet {SCHEMA_VERSION!r})."
        )

    taxonomie = None
    taxonomie_pfad = ziel_verzeichnis / "taxonomie.json"
    if taxonomie_pfad.exists():
        taxonomie = _json_laden(taxonomie_pfad, "taxonomie.json")
        taxonomie_fehler = validiere_gegen_schema(taxonomie, TAXONOMIE_SCHEMA)
        if taxonomie_fehler:
            raise PaketFehler("taxonomie.json ist ungültig: " + "; ".join(taxonomie_fehler))

    klausuren = []
    klausuren_verzeichnis = ziel_verzeichnis / "klausuren"
    if klausuren_verzeichnis.is_dir():
        for klausur_pfad in sorted(klausuren_verzeichnis.glob("*.json")):
            klausuren.append(_klausur_eintrag_laden(klausur_pfad, ziel_verzeichnis))

    return EntpacktesPaket(
        verzeichnis=ziel_verzeichnis, manifest=manifest, taxonomie=taxonomie, klausuren=klausuren
    )


def _klausur_eintrag_laden(klausur_pfad: Path, ziel_verzeichnis: Path) -> KlausurEintrag:
    daten = _json_laden(klausur_pfad, klausur_pfad.name)
    schema_fehler = validiere_gegen_schema(daten, KLAUSUR_SCHEMA)
    klausur_id = daten.get("id") or klausur_pfad.stem

    dateien_verzeichnis = ziel_verzeichnis / "dateien"
    pdf_pfad = dateien_verzeichnis / f"{klausur_id}.pdf"
    ewh_pfad = dateien_verzeichnis / f"{klausur_id}-ewh.pdf"

    if not pdf_pfad.exists():
        schema_fehler = [*schema_fehler, f"Datei dateien/{klausur_id}.pdf fehlt im Paket."]

    return KlausurEintrag(
        id=klausur_id,
        daten=daten,
        pdf_pfad=pdf_pfad if pdf_pfad.exists() else None,
        ewh_pdf_pfad=ewh_pfad if ewh_pfad.exists() else None,
        schema_fehler=schema_fehler,
    )


def _json_laden(pfad: Path, bezeichnung: str) -> dict:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaketFehler(f"{bezeichnung} ist kein gültiges JSON: {exc}") from exc


def _sicher_entpacken(zf: zipfile.ZipFile, ziel_verzeichnis: Path) -> None:
    """Schützt vor Zip-Slip: kein Eintrag darf außerhalb von ziel_verzeichnis landen."""
    ziel_verzeichnis = ziel_verzeichnis.resolve()
    for info in zf.infolist():
        ziel_pfad = (ziel_verzeichnis / info.filename).resolve()
        if ziel_pfad != ziel_verzeichnis and ziel_verzeichnis not in ziel_pfad.parents:
            raise PaketFehler(f"Unsicherer Pfad im Paket: {info.filename!r}.")
    zf.extractall(ziel_verzeichnis)
