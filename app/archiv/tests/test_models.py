import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from archiv.models import Fach, Klausur, Thema

from .conftest import dummy_pdf, erstelle_aufgabe, erstelle_teilaufgabe


@pytest.mark.django_db
def test_fach_kuerzel_ist_eindeutig():
    Fach.objects.create(name="Mathematik", kuerzel="M")
    with pytest.raises(IntegrityError):
        Fach.objects.create(name="Musik", kuerzel="M")


@pytest.mark.django_db
class TestThema:
    def test_kennung_ist_eindeutig_je_fach(self, fach_mathe):
        Thema.objects.create(fach=fach_mathe, kennung="analysis", name="Analysis")
        with pytest.raises(IntegrityError):
            Thema.objects.create(fach=fach_mathe, kennung="analysis", name="Analysis (doppelt)")

    def test_gleiche_kennung_in_anderem_fach_ist_erlaubt(self, fach_mathe, fach_deutsch):
        Thema.objects.create(fach=fach_mathe, kennung="analysis", name="Analysis")
        # Sollte keine IntegrityError auslösen, da die Kennung nur je Fach eindeutig sein muss.
        Thema.objects.create(fach=fach_deutsch, kennung="analysis", name="Zufällig gleicher Name")

    def test_eltern_thema_muss_zum_selben_fach_gehoeren(self, fach_mathe, fach_deutsch):
        eltern = Thema.objects.create(fach=fach_deutsch, kennung="lyrik", name="Lyrik")
        kind = Thema(fach=fach_mathe, eltern=eltern, kennung="analysis", name="Analysis")
        with pytest.raises(ValidationError):
            kind.full_clean()


@pytest.mark.django_db
class TestKlausur:
    def test_eindeutigkeit_ueber_fach_jahr_kursart_termin_variante(self, fach_mathe):
        Klausur.objects.create(
            fach=fach_mathe,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="A",
            titel="Analysis",
            pdf=dummy_pdf(),
        )
        with pytest.raises(IntegrityError):
            Klausur.objects.create(
                fach=fach_mathe,
                jahr=2024,
                kursart=Klausur.Kursart.LK,
                termin=Klausur.Termin.HAUPTTERMIN,
                variante="A",
                titel="Analysis (Duplikat)",
                pdf=dummy_pdf(),
            )

    def test_andere_variante_ist_keine_dopplung(self, fach_mathe):
        Klausur.objects.create(
            fach=fach_mathe,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="A",
            titel="Analysis A",
            pdf=dummy_pdf(),
        )
        # Sollte keine IntegrityError auslösen, da sich die Variante unterscheidet.
        Klausur.objects.create(
            fach=fach_mathe,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="B",
            titel="Analysis B",
            pdf=dummy_pdf(),
        )


@pytest.mark.django_db
class TestAufgabeUndTeilaufgabe:
    def test_aufgabennummer_ist_eindeutig_je_klausur(self, klausur_haupttermin):
        erstelle_aufgabe(klausur_haupttermin, nummer=1)
        with pytest.raises(IntegrityError):
            erstelle_aufgabe(klausur_haupttermin, nummer=1)

    def test_teilaufgaben_bezeichnung_ist_eindeutig_je_aufgabe(self, klausur_haupttermin):
        aufgabe = erstelle_aufgabe(klausur_haupttermin)
        erstelle_teilaufgabe(aufgabe, bezeichnung="1a")
        with pytest.raises(IntegrityError):
            erstelle_teilaufgabe(aufgabe, bezeichnung="1a")

    def test_teilaufgabe_kann_mehrere_themen_haben(self, klausur_haupttermin, fach_mathe):
        thema_1 = Thema.objects.create(fach=fach_mathe, kennung="a", name="A")
        thema_2 = Thema.objects.create(fach=fach_mathe, kennung="b", name="B")
        teilaufgabe = erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))

        teilaufgabe.themen.set([thema_1, thema_2])

        assert set(teilaufgabe.themen.all()) == {thema_1, thema_2}
