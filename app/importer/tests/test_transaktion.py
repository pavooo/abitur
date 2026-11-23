import pytest
from archiv.models import Aufgabe, Klausur, Teilaufgabe, Thema

from importer.models import Importprotokoll
from importer.paket import entpacken
from importer.transaktion import importiere_paket
from importer.vorschaubilder import vorschaubild_verzeichnis

from .conftest import klausur_json, manifest_fuer, schreibe_paket_zip, taxonomie_json


@pytest.mark.django_db
class TestImportiereePaket:
    def test_neue_klausur_wird_angelegt(self, tmp_path, fach_mathe, admin_lehrkraft):
        Thema.objects.create(fach=fach_mathe, kennung="analysis.diff.wendepunkt", name="Wendepunkt")
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[
                klausur_json(id="M-2024-LK-HT-A", fach="M", themen=["analysis.diff.wendepunkt"])
            ],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        protokoll = importiere_paket(paket, lehrkraft=admin_lehrkraft, paketname="paket.zip")

        assert protokoll.ergebnis == Importprotokoll.Ergebnis.ERFOLGREICH
        assert protokoll.anzahl_neu == 1
        assert protokoll.anzahl_aktualisiert == 0

        klausur = Klausur.objects.get(fach=fach_mathe, jahr=2024, kursart="LK", variante="A")
        assert klausur.titel == "Analysis"
        assert klausur.importprotokoll == protokoll
        assert klausur.hilfsmittel == Klausur.Hilfsmittel.TR
        aufgabe = Aufgabe.objects.get(klausur=klausur)
        assert aufgabe.pruefungsteil == Aufgabe.Pruefungsteil.MIT_HILFSMITTELN
        assert aufgabe.aufgabenbereich == Aufgabe.Aufgabenbereich.KEINE_ANGABE
        teilaufgabe = Teilaufgabe.objects.get(aufgabe=aufgabe)
        assert teilaufgabe.themen.filter(kennung="analysis.diff.wendepunkt").exists()

    def test_erneuter_import_aktualisiert_statt_dupliziert(
        self, tmp_path, fach_mathe, admin_lehrkraft
    ):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket1.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M", titel="Erste Version")],
        )
        paket1 = entpacken(zip_pfad, tmp_path / "inhalt1")
        importiere_paket(paket1, lehrkraft=admin_lehrkraft, paketname="paket1.zip")

        zip_pfad2 = schreibe_paket_zip(
            tmp_path / "paket2.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M", titel="Zweite Version")],
        )
        paket2 = entpacken(zip_pfad2, tmp_path / "inhalt2")
        protokoll2 = importiere_paket(paket2, lehrkraft=admin_lehrkraft, paketname="paket2.zip")

        assert protokoll2.anzahl_neu == 0
        assert protokoll2.anzahl_aktualisiert == 1
        klausuren = Klausur.objects.filter(fach=fach_mathe, jahr=2024, kursart="LK", variante="A")
        assert klausuren.count() == 1
        klausur = klausuren.get()
        assert klausur.titel == "Zweite Version"
        assert Aufgabe.objects.filter(klausur=klausur).count() == 1

    def test_importprotokoll_bleibt_bei_fehlschlag_erhalten(
        self, tmp_path, fach_mathe, admin_lehrkraft
    ):
        klausur_1 = klausur_json(id="M-2024-LK-HT-A", fach="M")
        # Zweite Klausur mit doppelter Aufgaben-Nummer provoziert eine IntegrityError
        # erst beim Schreiben (Vorschau prüft das bereits, hier wird die Transaktion
        # direkt getestet, als wäre die Prüfung übersprungen worden).
        klausur_2 = klausur_json(id="M-2024-LK-HT-B", fach="M", variante="B")
        klausur_2["aufgaben"].append(dict(klausur_2["aufgaben"][0]))

        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_1, klausur_2],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        protokoll = importiere_paket(paket, lehrkraft=admin_lehrkraft, paketname="paket.zip")

        assert protokoll.ergebnis == Importprotokoll.Ergebnis.FEHLGESCHLAGEN
        assert protokoll.fehlermeldung != ""
        assert Importprotokoll.objects.filter(pk=protokoll.pk).exists()
        # Die Transaktion wurde komplett zurückgerollt – auch die erste, an sich
        # gültige Klausur darf nicht teilweise übrig geblieben sein.
        assert Klausur.objects.filter(fach=fach_mathe).count() == 0

    def test_vorschaubilder_werden_fuer_klausur_pdf_erzeugt(
        self, tmp_path, fach_mathe, admin_lehrkraft
    ):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
            pdf_seiten_je_klausur={"M-2024-LK-HT-A": 3},
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        importiere_paket(paket, lehrkraft=admin_lehrkraft, paketname="paket.zip")

        klausur = Klausur.objects.get(fach=fach_mathe)
        verzeichnis = vorschaubild_verzeichnis(klausur)
        erzeugte_dateien = sorted(p.name for p in verzeichnis.glob("*.png"))
        assert erzeugte_dateien == ["seite-1.png", "seite-2.png", "seite-3.png"]

    def test_taxonomie_wird_vor_klausuren_importiert(self, tmp_path, fach_mathe, admin_lehrkraft):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            taxonomie=taxonomie_json(
                "M",
                [
                    {"kennung": "analysis", "name": "Analysis"},
                    {
                        "kennung": "analysis.diff.wendepunkt",
                        "name": "Wendepunkt",
                        "eltern": "analysis",
                        "kursniveau": "LK",
                    },
                ],
            ),
            klausuren=[
                klausur_json(id="M-2024-LK-HT-A", fach="M", themen=["analysis.diff.wendepunkt"])
            ],
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        protokoll = importiere_paket(paket, lehrkraft=admin_lehrkraft, paketname="paket.zip")

        assert protokoll.ergebnis == Importprotokoll.Ergebnis.ERFOLGREICH
        eltern = Thema.objects.get(fach=fach_mathe, kennung="analysis")
        kind = Thema.objects.get(fach=fach_mathe, kennung="analysis.diff.wendepunkt")
        assert kind.eltern == eltern
        assert kind.kursniveau == Thema.Kursniveau.LK

    def test_taxonomie_update_aktualisiert_bestehendes_thema(
        self, tmp_path, fach_mathe, admin_lehrkraft
    ):
        Thema.objects.create(fach=fach_mathe, kennung="analysis", name="Alter Name")
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            taxonomie=taxonomie_json("M", [{"kennung": "analysis", "name": "Neuer Name"}]),
        )
        paket = entpacken(zip_pfad, tmp_path / "inhalt")

        importiere_paket(paket, lehrkraft=admin_lehrkraft, paketname="paket.zip")

        thema = Thema.objects.get(fach=fach_mathe, kennung="analysis")
        assert thema.name == "Neuer Name"
        assert Thema.objects.filter(fach=fach_mathe, kennung="analysis").count() == 1
