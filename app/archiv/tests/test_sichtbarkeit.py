"""Pflicht-Tests für die zentrale Sichtbarkeitslogik (CLAUDE.md,
Abschnitt Nachschreibklausuren – SICHERHEITSKRITISCH).

Stellt sicher, dass SuS unter keinen Umständen Nachschreibklausuren sehen –
auch nicht im eigenen Fach – und dass Lehrkräfte nur ihre zugeordneten
Fächer sehen, Nachschreibklausuren nur im aktivierten Nachschreibmodus.
"""

import pytest

from archiv.models import Aufgabe, Klausur, Teilaufgabe

from .conftest import erstelle_aufgabe, erstelle_klausur, erstelle_teilaufgabe


@pytest.mark.django_db
class TestKlausurSichtbarFuer:
    def test_sus_sieht_haupttermin_des_eigenen_fachs(
        self, sus_request, klausur_haupttermin, klausur_nachschreibtermin, klausur_anderes_fach
    ):
        sichtbar = Klausur.objects.sichtbar_fuer(sus_request)
        assert list(sichtbar) == [klausur_haupttermin]

    def test_sus_sieht_niemals_nachschreibtermin(
        self, sus_request, klausur_haupttermin, klausur_nachschreibtermin
    ):
        sichtbar = Klausur.objects.sichtbar_fuer(sus_request)
        assert klausur_nachschreibtermin not in sichtbar

    def test_sus_sieht_keine_fachfremden_klausuren(self, sus_request, klausur_anderes_fach):
        sichtbar = Klausur.objects.sichtbar_fuer(sus_request)
        assert klausur_anderes_fach not in sichtbar

    def test_lehrkraft_sieht_im_normalmodus_keine_nachschreibklausur(
        self,
        lehrkraft_request_factory,
        fach_mathe,
        klausur_haupttermin,
        klausur_nachschreibtermin,
    ):
        request = lehrkraft_request_factory(faecher=[fach_mathe])
        sichtbar = Klausur.objects.sichtbar_fuer(request)
        assert list(sichtbar) == [klausur_haupttermin]

    def test_lehrkraft_sieht_im_nachschreibmodus_beide_termine(
        self,
        lehrkraft_request_factory,
        fach_mathe,
        klausur_haupttermin,
        klausur_nachschreibtermin,
    ):
        request = lehrkraft_request_factory(faecher=[fach_mathe], nachschreibmodus=True)
        sichtbar = Klausur.objects.sichtbar_fuer(request)
        assert set(sichtbar) == {klausur_haupttermin, klausur_nachschreibtermin}

    def test_lehrkraft_sieht_nie_fachfremde_klausuren_auch_im_nachschreibmodus(
        self, lehrkraft_request_factory, fach_mathe, klausur_anderes_fach
    ):
        request = lehrkraft_request_factory(faecher=[fach_mathe], nachschreibmodus=True)
        sichtbar = Klausur.objects.sichtbar_fuer(request)
        assert klausur_anderes_fach not in sichtbar

    def test_lehrkraft_ohne_zugeordnete_faecher_sieht_nichts(
        self, lehrkraft_request_factory, klausur_haupttermin, klausur_nachschreibtermin
    ):
        request = lehrkraft_request_factory(faecher=[], nachschreibmodus=True)
        sichtbar = Klausur.objects.sichtbar_fuer(request)
        assert sichtbar.count() == 0

    def test_admin_lehrkraft_sieht_nur_eigene_faecher_keine_ausnahme(
        self, lehrkraft_request_factory, fach_mathe, klausur_anderes_fach, klausur_haupttermin
    ):
        request = lehrkraft_request_factory(faecher=[fach_mathe], ist_admin=True)
        sichtbar = Klausur.objects.sichtbar_fuer(request)
        assert list(sichtbar) == [klausur_haupttermin]
        assert klausur_anderes_fach not in sichtbar

    def test_anonym_sieht_nichts(
        self, anonymer_request, klausur_haupttermin, klausur_nachschreibtermin
    ):
        sichtbar = Klausur.objects.sichtbar_fuer(anonymer_request)
        assert sichtbar.count() == 0


@pytest.mark.django_db
class TestKlausurSichtbarFuerStatus:
    """Pflicht-Tests für den Freigabe-Status aus dem Lehrkraft-Editor (CLAUDE.md,
    Abschnitt Lehrkraft-Editor): Entwürfe/eingereichte/abgelehnte Klausuren dürfen
    niemals für SuS oder fachfremde/andere Lehrkräfte sichtbar sein."""

    @pytest.mark.parametrize(
        "status",
        [Klausur.Status.ENTWURF, Klausur.Status.EINGEREICHT, Klausur.Status.ABGELEHNT],
    )
    def test_sus_sieht_niemals_unfreigegebene_klausur(self, sus_request, fach_mathe, status):
        klausur = erstelle_klausur(fach_mathe, status=status, variante=status)
        assert klausur not in Klausur.objects.sichtbar_fuer(sus_request)

    def test_sus_sieht_freigegebene_klausur(self, sus_request, fach_mathe):
        klausur = erstelle_klausur(fach_mathe, status=Klausur.Status.FREIGEGEBEN)
        assert klausur in Klausur.objects.sichtbar_fuer(sus_request)

    def test_lehrkraft_sieht_eigene_klausur_unabhaengig_vom_status(
        self, lehrkraft_request_factory, fach_mathe
    ):
        request = lehrkraft_request_factory(faecher=[fach_mathe])
        entwurf = erstelle_klausur(
            fach_mathe, status=Klausur.Status.ENTWURF, ersteller=request.user, variante="eigen"
        )
        assert entwurf in Klausur.objects.sichtbar_fuer(request)

    def test_lehrkraft_sieht_keine_entwuerfe_anderer_lehrkraft(
        self, lehrkraft_request_factory, fach_mathe
    ):
        lehrkraft_a = lehrkraft_request_factory(faecher=[fach_mathe])
        lehrkraft_b = lehrkraft_request_factory(faecher=[fach_mathe])
        entwurf_a = erstelle_klausur(
            fach_mathe, status=Klausur.Status.ENTWURF, ersteller=lehrkraft_a.user, variante="a"
        )
        assert entwurf_a not in Klausur.objects.sichtbar_fuer(lehrkraft_b)

    def test_lehrkraft_sieht_keine_eingereichten_klausuren_anderer_lehrkraft(
        self, lehrkraft_request_factory, fach_mathe
    ):
        lehrkraft_a = lehrkraft_request_factory(faecher=[fach_mathe])
        lehrkraft_b = lehrkraft_request_factory(faecher=[fach_mathe])
        eingereicht_a = erstelle_klausur(
            fach_mathe,
            status=Klausur.Status.EINGEREICHT,
            ersteller=lehrkraft_a.user,
            variante="eingereicht-a",
        )
        assert eingereicht_a not in Klausur.objects.sichtbar_fuer(lehrkraft_b)

    def test_admin_sieht_eingereichte_klausuren_im_eigenen_fach(
        self, lehrkraft_request_factory, fach_mathe
    ):
        lehrkraft = lehrkraft_request_factory(faecher=[fach_mathe])
        admin = lehrkraft_request_factory(faecher=[fach_mathe], ist_admin=True)
        eingereicht = erstelle_klausur(
            fach_mathe,
            status=Klausur.Status.EINGEREICHT,
            ersteller=lehrkraft.user,
            variante="zur-pruefung",
        )
        assert eingereicht in Klausur.objects.sichtbar_fuer(admin)

    def test_admin_sieht_keine_eingereichten_klausuren_fachfremder_lehrkraft(
        self, lehrkraft_request_factory, fach_mathe, fach_deutsch
    ):
        lehrkraft = lehrkraft_request_factory(faecher=[fach_deutsch])
        admin = lehrkraft_request_factory(faecher=[fach_mathe], ist_admin=True)
        eingereicht = erstelle_klausur(
            fach_deutsch,
            status=Klausur.Status.EINGEREICHT,
            ersteller=lehrkraft.user,
            variante="fachfremd",
        )
        assert eingereicht not in Klausur.objects.sichtbar_fuer(admin)

    def test_sus_sieht_keine_aufgaben_unfreigegebener_klausur(self, sus_request, fach_mathe):
        entwurf = erstelle_klausur(fach_mathe, status=Klausur.Status.ENTWURF, variante="aufgabe")
        aufgabe = erstelle_aufgabe(entwurf)
        assert aufgabe not in Aufgabe.objects.sichtbar_fuer(sus_request)


@pytest.mark.django_db
class TestAufgabeUndTeilaufgabeSichtbarFuer:
    def test_sus_sieht_keine_aufgaben_der_nachschreibklausur(
        self, sus_request, klausur_haupttermin, klausur_nachschreibtermin
    ):
        aufgabe_haupttermin = erstelle_aufgabe(klausur_haupttermin)
        aufgabe_nachschreiber = erstelle_aufgabe(klausur_nachschreibtermin)

        sichtbar = Aufgabe.objects.sichtbar_fuer(sus_request)

        assert list(sichtbar) == [aufgabe_haupttermin]
        assert aufgabe_nachschreiber not in sichtbar

    def test_sus_sieht_keine_teilaufgaben_der_nachschreibklausur(
        self, sus_request, klausur_haupttermin, klausur_nachschreibtermin
    ):
        teilaufgabe_haupttermin = erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
        aufgabe_nachschreiber = erstelle_aufgabe(klausur_nachschreibtermin)
        teilaufgabe_nachschreiber = erstelle_teilaufgabe(aufgabe_nachschreiber)

        sichtbar = Teilaufgabe.objects.sichtbar_fuer(sus_request)

        assert list(sichtbar) == [teilaufgabe_haupttermin]
        assert teilaufgabe_nachschreiber not in sichtbar

    def test_lehrkraft_sieht_teilaufgaben_der_nachschreibklausur_nur_im_nachschreibmodus(
        self, lehrkraft_request_factory, fach_mathe, klausur_haupttermin, klausur_nachschreibtermin
    ):
        aufgabe_nachschreiber = erstelle_aufgabe(klausur_nachschreibtermin)
        teilaufgabe_nachschreiber = erstelle_teilaufgabe(aufgabe_nachschreiber)

        normalmodus = lehrkraft_request_factory(faecher=[fach_mathe])
        assert teilaufgabe_nachschreiber not in Teilaufgabe.objects.sichtbar_fuer(normalmodus)

        nachschreibmodus = lehrkraft_request_factory(faecher=[fach_mathe], nachschreibmodus=True)
        assert teilaufgabe_nachschreiber in Teilaufgabe.objects.sichtbar_fuer(nachschreibmodus)

    def test_anonym_sieht_keine_aufgaben_oder_teilaufgaben(
        self, anonymer_request, klausur_haupttermin
    ):
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))

        assert Aufgabe.objects.sichtbar_fuer(anonymer_request).count() == 0
        assert Teilaufgabe.objects.sichtbar_fuer(anonymer_request).count() == 0
