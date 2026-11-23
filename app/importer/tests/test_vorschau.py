import pytest
from archiv.models import Fach, Klausur, Thema

from importer.paket import entpacken
from importer.vorschau import berechne_vorschau

from .conftest import klausur_json, manifest_fuer, schreibe_paket_zip


@pytest.mark.django_db
class TestVorschau:
    def test_neue_klausur_wird_als_neu_markiert(self, tmp_path, fach_mathe):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.hat_fehler is False
        assert vorschau.zeilen[0].status == "neu"

    def test_bestehende_klausur_wird_als_aktualisiert_markiert(self, tmp_path, fach_mathe):
        Klausur.objects.create(
            fach=fach_mathe,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="A",
            titel="Alt",
            pdf="klausuren/alt.pdf",
        )
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.zeilen[0].status == "aktualisiert"

    def test_unbekanntes_fach_kuerzel_ist_allgemeiner_fehler(self, tmp_path, db):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("X"),
            klausuren=[klausur_json(id="X-2024-LK-HT-A", fach="X")],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.hat_fehler is True
        assert any("Unbekanntes Fach-Kürzel" in fehler for fehler in vorschau.allgemeine_fehler)

    def test_unbekannte_themen_kennung_ist_fehler(self, tmp_path, fach_mathe):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[
                klausur_json(id="M-2024-LK-HT-A", fach="M", themen=["analysis.nicht.vorhanden"])
            ],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.hat_fehler is True
        assert vorschau.zeilen[0].status == "fehler"
        assert any("unbekannte Themen-Kennung" in f for f in vorschau.zeilen[0].fehler)

    def test_bereits_existierende_themen_kennung_ist_gueltig(self, tmp_path, fach_mathe):
        Thema.objects.create(fach=fach_mathe, kennung="analysis.diff.wendepunkt", name="Wendepunkt")
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[
                klausur_json(id="M-2024-LK-HT-A", fach="M", themen=["analysis.diff.wendepunkt"])
            ],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.hat_fehler is False

    def test_themen_kennung_aus_mitgelieferter_taxonomie_ist_gueltig(self, tmp_path, fach_mathe):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            taxonomie={
                "fach": "M",
                "themen": [{"kennung": "analysis.diff.wendepunkt", "name": "Wendepunkt"}],
            },
            klausuren=[
                klausur_json(id="M-2024-LK-HT-A", fach="M", themen=["analysis.diff.wendepunkt"])
            ],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.hat_fehler is False
        assert vorschau.taxonomie_themen_anzahl == 1

    def test_fach_der_klausur_weicht_vom_manifest_ab(self, tmp_path, fach_mathe):
        Fach.objects.create(name="Deutsch", kuerzel="D")
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="D-2024-LK-HT-A", fach="D")],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.hat_fehler is True
        assert any("weicht vom Paket-Fach" in f for f in vorschau.zeilen[0].fehler)

    def test_ein_fehler_blockiert_das_gesamte_paket(self, tmp_path, fach_mathe):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[
                klausur_json(id="M-2024-LK-HT-A", fach="M"),
                klausur_json(
                    id="M-2024-GK-HT-A",
                    fach="M",
                    kursart="GK",
                    themen=["unbekannt.kennung"],
                ),
            ],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        vorschau = berechne_vorschau(paket)

        assert vorschau.hat_fehler is True
        status_je_id = {zeile.id: zeile.status for zeile in vorschau.zeilen}
        assert status_je_id["M-2024-LK-HT-A"] == "neu"
        assert status_je_id["M-2024-GK-HT-A"] == "fehler"
