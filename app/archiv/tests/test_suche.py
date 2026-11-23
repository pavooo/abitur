"""Tests für Suchvektor-Pflege (Signals) und die Such-Helfer in `archiv/suche.py`."""

import pytest

from archiv.models import Teilaufgabe, Thema
from archiv.suche import volltext_filtern

from .conftest import erstelle_aufgabe, erstelle_teilaufgabe


@pytest.mark.django_db
class TestSuchvektorPflege:
    def test_such_vektor_wird_beim_speichern_gesetzt(self, klausur_haupttermin):
        aufgabe = erstelle_aufgabe(klausur_haupttermin)
        teilaufgabe = Teilaufgabe.objects.create(
            aufgabe=aufgabe,
            bezeichnung="1a",
            text="Berechnen Sie den Wendepunkt der Funktion.",
            seite=1,
            anforderungsbereich=Teilaufgabe.Anforderungsbereich.II,
        )
        teilaufgabe.refresh_from_db()
        assert teilaufgabe.such_vektor is not None

    def test_such_vektor_erfasst_themennamen_und_synonyme(self, fach_mathe, klausur_haupttermin):
        thema = Thema.objects.create(
            fach=fach_mathe,
            kennung="analysis.extrempunkte",
            name="Extrempunkte",
            synonyme=["Hochpunkt", "Tiefpunkt"],
        )
        teilaufgabe = erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
        teilaufgabe.themen.add(thema)

        treffer = volltext_filtern(Teilaufgabe.objects.all(), "Hochpunkt")
        assert teilaufgabe in treffer


@pytest.mark.django_db
class TestVolltextFiltern:
    def test_findet_exakten_text(self, klausur_haupttermin):
        aufgabe = erstelle_aufgabe(klausur_haupttermin)
        gesucht = Teilaufgabe.objects.create(
            aufgabe=aufgabe,
            bezeichnung="1a",
            text="Berechnen Sie das Integral der Funktion f.",
            seite=1,
            anforderungsbereich=Teilaufgabe.Anforderungsbereich.I,
        )
        anderer = Teilaufgabe.objects.create(
            aufgabe=aufgabe,
            bezeichnung="1b",
            text="Bestimmen Sie die Nullstellen von g.",
            seite=1,
            anforderungsbereich=Teilaufgabe.Anforderungsbereich.I,
        )

        treffer = volltext_filtern(Teilaufgabe.objects.all(), "Integral")
        assert list(treffer) == [gesucht]
        assert anderer not in treffer

    def test_leerer_suchtext_liefert_unveraendertes_queryset(self, klausur_haupttermin):
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
        ergebnis = volltext_filtern(Teilaufgabe.objects.all(), "")
        assert ergebnis.count() == Teilaufgabe.objects.count()

    def test_tippfehler_wird_ueber_trigram_aehnlichkeit_gefunden(self, klausur_haupttermin):
        aufgabe = erstelle_aufgabe(klausur_haupttermin)
        teilaufgabe = Teilaufgabe.objects.create(
            aufgabe=aufgabe,
            bezeichnung="1a",
            text="Berechnen Sie den Wert des Integrals.",
            seite=1,
            anforderungsbereich=Teilaufgabe.Anforderungsbereich.I,
        )

        treffer = volltext_filtern(Teilaufgabe.objects.all(), "Integarl")
        assert teilaufgabe in treffer


@pytest.mark.django_db
class TestInThema:
    def test_erfasst_thema_selbst_und_unterthemen(self, fach_mathe, klausur_haupttermin):
        eltern = Thema.objects.create(fach=fach_mathe, kennung="analysis", name="Analysis")
        kind = Thema.objects.create(
            fach=fach_mathe, kennung="analysis.diff", name="Differentialrechnung", eltern=eltern
        )
        fachfremdes_thema = Thema.objects.create(
            fach=fach_mathe, kennung="stochastik", name="Stochastik"
        )

        teilaufgabe_kind = erstelle_teilaufgabe(
            erstelle_aufgabe(klausur_haupttermin), bezeichnung="1a"
        )
        teilaufgabe_kind.themen.add(kind)
        teilaufgabe_eltern = erstelle_teilaufgabe(
            erstelle_aufgabe(klausur_haupttermin, nummer=2), bezeichnung="2a"
        )
        teilaufgabe_eltern.themen.add(eltern)
        teilaufgabe_fachfremd = erstelle_teilaufgabe(
            erstelle_aufgabe(klausur_haupttermin, nummer=3), bezeichnung="3a"
        )
        teilaufgabe_fachfremd.themen.add(fachfremdes_thema)

        treffer = set(Teilaufgabe.objects.in_thema("analysis"))
        assert treffer == {teilaufgabe_kind, teilaufgabe_eltern}

    def test_praefix_trifft_keine_unverwandten_kennungen(self, fach_mathe, klausur_haupttermin):
        Thema.objects.create(fach=fach_mathe, kennung="analysis", name="Analysis")
        thema_aehnlich = Thema.objects.create(
            fach=fach_mathe, kennung="analysisfremd", name="Analysisfremd"
        )
        teilaufgabe = erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
        teilaufgabe.themen.add(thema_aehnlich)

        treffer = Teilaufgabe.objects.in_thema("analysis")
        assert teilaufgabe not in treffer
