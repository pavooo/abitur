import zipfile

import pytest

from importer.paket import PaketFehler, entpacken

from .conftest import klausur_json, manifest_fuer, schreibe_paket_zip


def test_entpacken_liest_manifest_und_klausuren(tmp_path):
    zip_pfad = schreibe_paket_zip(
        tmp_path / "paket.zip",
        manifest=manifest_fuer("M"),
        klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
    )

    paket = entpacken(zip_pfad, tmp_path / "inhalt")

    assert paket.manifest["fach"] == "M"
    assert len(paket.klausuren) == 1
    assert paket.klausuren[0].id == "M-2024-LK-HT-A"
    assert paket.klausuren[0].pdf_pfad is not None
    assert paket.klausuren[0].schema_fehler == []


def test_entpacken_ohne_manifest_schlaegt_fehl(tmp_path):
    zip_pfad = tmp_path / "paket.zip"
    with zipfile.ZipFile(zip_pfad, "w") as zf:
        zf.writestr("nichts.txt", "leer")

    with pytest.raises(PaketFehler, match="manifest.json"):
        entpacken(zip_pfad, tmp_path / "inhalt")


def test_entpacken_mit_falscher_schema_version_schlaegt_fehl(tmp_path):
    zip_pfad = schreibe_paket_zip(
        tmp_path / "paket.zip",
        manifest=manifest_fuer("M", schema_version="99.0"),
    )

    with pytest.raises(PaketFehler, match="Schema-Version"):
        entpacken(zip_pfad, tmp_path / "inhalt")


def test_entpacken_mit_ungueltigem_manifest_schlaegt_fehl(tmp_path):
    zip_pfad = tmp_path / "paket.zip"
    with zipfile.ZipFile(zip_pfad, "w") as zf:
        zf.writestr("manifest.json", "{}")

    with pytest.raises(PaketFehler, match="manifest.json ist ungültig"):
        entpacken(zip_pfad, tmp_path / "inhalt")


def test_entpacken_schuetzt_vor_zip_slip(tmp_path):
    zip_pfad = tmp_path / "boese.zip"
    with zipfile.ZipFile(zip_pfad, "w") as zf:
        zf.writestr(
            "manifest.json",
            '{"schema_version": "1.0", "fach": "M", "erstellt_am": "2026-01-01"}',
        )
        zf.writestr("../../ausserhalb.txt", "böse")

    with pytest.raises(PaketFehler, match="Unsicherer Pfad"):
        entpacken(zip_pfad, tmp_path / "inhalt")


def test_entpacken_klausur_ohne_pdf_meldet_schema_fehler(tmp_path):
    zip_pfad = schreibe_paket_zip(
        tmp_path / "paket.zip",
        manifest=manifest_fuer("M"),
        klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        ohne_pdf={"M-2024-LK-HT-A"},
    )

    paket = entpacken(zip_pfad, tmp_path / "inhalt")

    assert paket.klausuren[0].pdf_pfad is None
    assert any("fehlt im Paket" in fehler for fehler in paket.klausuren[0].schema_fehler)


def test_entpacken_meldet_ungueltige_klausur_als_schema_fehler(tmp_path):
    zip_pfad = schreibe_paket_zip(
        tmp_path / "paket.zip",
        manifest=manifest_fuer("M"),
        klausuren=[{"id": "kaputt", "fach": "M"}],  # Pflichtfelder fehlen
    )

    paket = entpacken(zip_pfad, tmp_path / "inhalt")

    assert paket.klausuren[0].schema_fehler != []


def test_entpacken_ohne_taxonomie_ist_optional(tmp_path):
    zip_pfad = schreibe_paket_zip(tmp_path / "paket.zip", manifest=manifest_fuer("M"))
    paket = entpacken(zip_pfad, tmp_path / "inhalt")
    assert paket.taxonomie is None
