"""View-Tests für Suche, Themenbrowser, Klausuransicht, Dateiauslieferung und
Nachschreibmodus (Phase 5).

Pflicht-Tests nach CLAUDE.md (Abschnitt Nachschreibklausuren): für jede Route,
die Klausurdaten ausgibt, muss sichergestellt sein, dass ein SuS-Login keine
Nachschreibklausur sieht – weder in Suche/Themenbrowser-Treffern noch über die
Klausuransicht, PDF-/Erwartungshorizont-Auslieferung oder Vorschaubilder.
"""

import pytest
from django.urls import reverse

from archiv.models import Klausur, NachschreibZugriff, Thema
from archiv.sichtbarkeit import NACHSCHREIBMODUS_SESSION_KEY

from .conftest import dummy_pdf, erstelle_aufgabe, erstelle_teilaufgabe


@pytest.fixture
def thema_eltern(fach_mathe):
    return Thema.objects.create(fach=fach_mathe, kennung="analysis", name="Analysis")


@pytest.fixture
def thema_wendepunkt(fach_mathe, thema_eltern):
    return Thema.objects.create(
        fach=fach_mathe,
        kennung="analysis.wendepunkt",
        name="Wendepunkte",
        eltern=thema_eltern,
    )


def _klausuren_aus_seite(response):
    return [eintrag["klausur"] for eintrag in response.context["seite_obj"]]


@pytest.mark.django_db
class TestSucheNachschreibPflicht:
    def test_sus_sieht_in_suche_keine_nachschreibklausur(
        self, sus_client, klausur_haupttermin, klausur_nachschreibtermin
    ):
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_nachschreibtermin))

        # hilfsmittel="" deaktiviert den Standardfilter (sonst Default "CAS"),
        # die Fixtures legen Klausuren mit Hilfsmittel "TR" an.
        response = sus_client.get(reverse("archiv:suche"), {"hilfsmittel": ""})

        klausuren = _klausuren_aus_seite(response)
        assert klausur_nachschreibtermin not in klausuren
        assert klausur_haupttermin in klausuren

    def test_sus_sieht_keine_nachschreibklausur_auch_mit_termin_parameter(
        self, sus_client, klausur_nachschreibtermin
    ):
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_nachschreibtermin))
        response = sus_client.get(
            reverse("archiv:suche"), {"termin": "nachschreibtermin", "hilfsmittel": ""}
        )
        assert klausur_nachschreibtermin not in _klausuren_aus_seite(response)

    def test_lehrkraft_sieht_nachschreibklausur_nur_im_nachschreibmodus(
        self, lehrkraft_client_factory, fach_mathe, klausur_nachschreibtermin
    ):
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_nachschreibtermin))

        normalmodus = lehrkraft_client_factory(faecher=[fach_mathe])
        response = normalmodus.get(reverse("archiv:suche"), {"hilfsmittel": ""})
        assert klausur_nachschreibtermin not in _klausuren_aus_seite(response)

        nachschreibmodus = lehrkraft_client_factory(faecher=[fach_mathe], nachschreibmodus=True)
        response = nachschreibmodus.get(reverse("archiv:suche"), {"hilfsmittel": ""})
        assert klausur_nachschreibtermin in _klausuren_aus_seite(response)

    def test_nur_hilfsmittelfrei_filter(
        self, lehrkraft_client_factory, fach_mathe, klausur_haupttermin
    ):
        from archiv.models import Aufgabe

        hilfsmittelfrei = erstelle_aufgabe(klausur_haupttermin, nummer=1)
        hilfsmittelfrei.pruefungsteil = Aufgabe.Pruefungsteil.HILFSMITTELFREI
        hilfsmittelfrei.save()
        teilaufgabe_frei = erstelle_teilaufgabe(hilfsmittelfrei, bezeichnung="1a")

        mit_hilfsmitteln = erstelle_aufgabe(klausur_haupttermin, nummer=2)
        erstelle_teilaufgabe(mit_hilfsmitteln, bezeichnung="2a")

        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(reverse("archiv:suche"), {"nur_hilfsmittelfrei": "1"})

        gruppen = response.context["seite_obj"].object_list
        teilaufgaben = [t for eintrag in gruppen for t in eintrag["teilaufgaben"]]
        assert teilaufgaben == [teilaufgabe_frei]


@pytest.mark.django_db
class TestHilfsmittelUndJahrFilter:
    def test_ohne_parameter_ist_cas_voreingestellt(self, lehrkraft_client_factory, fach_mathe):
        klausur_cas = Klausur.objects.create(
            fach=fach_mathe,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            titel="CAS-Klausur",
            hilfsmittel=Klausur.Hilfsmittel.CAS,
            pdf=dummy_pdf("cas.pdf"),
        )
        klausur_tr = Klausur.objects.create(
            fach=fach_mathe,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="TR",
            titel="TR-Klausur",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=dummy_pdf("tr.pdf"),
        )
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_cas))
        erstelle_teilaufgabe(erstelle_aufgabe(klausur_tr))

        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(reverse("archiv:suche"))

        klausuren = _klausuren_aus_seite(response)
        assert klausur_cas in klausuren
        assert klausur_tr not in klausuren

    def test_nur_hilfsmittelfrei_ignoriert_hilfsmittel_default(
        self, lehrkraft_client_factory, fach_mathe, klausur_haupttermin
    ):
        from archiv.models import Aufgabe

        # Fixture nutzt hilfsmittel="TR"; ohne Sonderbehandlung würde der
        # CAS-Default hilfsmittelfreie Treffer dieser Klausur verstecken.
        hilfsmittelfrei = erstelle_aufgabe(klausur_haupttermin)
        hilfsmittelfrei.pruefungsteil = Aufgabe.Pruefungsteil.HILFSMITTELFREI
        hilfsmittelfrei.save()
        teilaufgabe = erstelle_teilaufgabe(hilfsmittelfrei)

        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(reverse("archiv:suche"), {"nur_hilfsmittelfrei": "1"})

        gruppen = response.context["seite_obj"].object_list
        teilaufgaben = [t for eintrag in gruppen for t in eintrag["teilaufgaben"]]
        assert teilaufgabe in teilaufgaben

    def test_jahr_liste_enthaelt_nur_sichtbare_jahre_absteigend(
        self, lehrkraft_client_factory, fach_mathe
    ):
        for jahr in (2022, 2024, 2023):
            Klausur.objects.create(
                fach=fach_mathe,
                jahr=jahr,
                kursart=Klausur.Kursart.LK,
                termin=Klausur.Termin.HAUPTTERMIN,
                variante=str(jahr),
                titel=f"Klausur {jahr}",
                hilfsmittel=Klausur.Hilfsmittel.CAS,
                pdf=dummy_pdf(f"{jahr}.pdf"),
            )

        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(reverse("archiv:suche"))

        assert list(response.context["jahre"]) == [2024, 2023, 2022]


@pytest.mark.django_db
class TestThemenbrowserNachschreibPflicht:
    def test_sus_sieht_im_themenbrowser_keine_nachschreibklausur(
        self,
        sus_client,
        klausur_haupttermin,
        klausur_nachschreibtermin,
        thema_wendepunkt,
    ):
        teilaufgabe_haupt = erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
        teilaufgabe_haupt.themen.add(thema_wendepunkt)
        teilaufgabe_nt = erstelle_teilaufgabe(erstelle_aufgabe(klausur_nachschreibtermin))
        teilaufgabe_nt.themen.add(thema_wendepunkt)

        response = sus_client.get(
            reverse("archiv:themenbrowser"), {"thema": thema_wendepunkt.kennung}
        )

        klausuren = _klausuren_aus_seite(response)
        assert klausur_nachschreibtermin not in klausuren
        assert klausur_haupttermin in klausuren

    def test_filter_erfasst_unterthemen(
        self,
        lehrkraft_client_factory,
        fach_mathe,
        klausur_haupttermin,
        thema_eltern,
        thema_wendepunkt,
    ):
        teilaufgabe = erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
        teilaufgabe.themen.add(thema_wendepunkt)

        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(
            reverse("archiv:themenbrowser"), {"thema": thema_eltern.kennung}
        )

        assert klausur_haupttermin in _klausuren_aus_seite(response)


@pytest.mark.django_db
class TestKlausurDetailNachschreibPflicht:
    def test_sus_erhaelt_404_fuer_nachschreibklausur(self, sus_client, klausur_nachschreibtermin):
        response = sus_client.get(
            reverse("archiv:klausur_detail", args=[klausur_nachschreibtermin.pk])
        )
        assert response.status_code == 404

    def test_sus_sieht_haupttermin_klausur(self, sus_client, klausur_haupttermin):
        response = sus_client.get(reverse("archiv:klausur_detail", args=[klausur_haupttermin.pk]))
        assert response.status_code == 200

    def test_lehrkraft_erhaelt_404_ohne_nachschreibmodus(
        self, lehrkraft_client_factory, fach_mathe, klausur_nachschreibtermin
    ):
        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(
            reverse("archiv:klausur_detail", args=[klausur_nachschreibtermin.pk])
        )
        assert response.status_code == 404

    def test_lehrkraft_sieht_nachschreibklausur_im_nachschreibmodus(
        self, lehrkraft_client_factory, fach_mathe, klausur_nachschreibtermin
    ):
        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe], nachschreibmodus=True)
        response = lehrkraft_client.get(
            reverse("archiv:klausur_detail", args=[klausur_nachschreibtermin.pk])
        )
        assert response.status_code == 200

    def test_zugriff_auf_nachschreibklausur_wird_protokolliert(
        self, lehrkraft_client_factory, fach_mathe, klausur_nachschreibtermin
    ):
        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe], nachschreibmodus=True)
        lehrkraft_client.get(reverse("archiv:klausur_detail", args=[klausur_nachschreibtermin.pk]))
        assert NachschreibZugriff.objects.filter(klausur=klausur_nachschreibtermin).count() == 1

    def test_zugriff_auf_haupttermin_klausur_wird_nicht_protokolliert(
        self, lehrkraft_client_factory, fach_mathe, klausur_haupttermin
    ):
        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        lehrkraft_client.get(reverse("archiv:klausur_detail", args=[klausur_haupttermin.pk]))
        assert NachschreibZugriff.objects.count() == 0


@pytest.mark.django_db
class TestKlausurDateiUndVorschaubildNachschreibPflicht:
    def test_sus_erhaelt_404_fuer_pdf_der_nachschreibklausur(
        self, sus_client, klausur_nachschreibtermin
    ):
        response = sus_client.get(
            reverse("archiv:klausur_datei", args=[klausur_nachschreibtermin.pk, "pdf"])
        )
        assert response.status_code == 404

    def test_sus_erhaelt_404_fuer_vorschaubild_der_nachschreibklausur(
        self, sus_client, klausur_nachschreibtermin
    ):
        response = sus_client.get(
            reverse("archiv:vorschaubild", args=[klausur_nachschreibtermin.pk, 1])
        )
        assert response.status_code == 404

    def test_sus_kann_pdf_der_haupttermin_klausur_laden(self, sus_client, klausur_haupttermin):
        response = sus_client.get(
            reverse("archiv:klausur_datei", args=[klausur_haupttermin.pk, "pdf"])
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_sus_erhaelt_404_fuer_erwartungshorizont(self, sus_client, klausur_haupttermin):
        response = sus_client.get(
            reverse("archiv:klausur_datei", args=[klausur_haupttermin.pk, "erwartungshorizont"])
        )
        assert response.status_code == 404

    def test_lehrkraft_ohne_erwartungshorizont_datei_erhaelt_404(
        self, lehrkraft_client_factory, fach_mathe, klausur_haupttermin
    ):
        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(
            reverse("archiv:klausur_datei", args=[klausur_haupttermin.pk, "erwartungshorizont"])
        )
        assert response.status_code == 404

    def test_unbekannte_dateiart_ergibt_404(
        self, lehrkraft_client_factory, fach_mathe, klausur_haupttermin
    ):
        lehrkraft_client = lehrkraft_client_factory(faecher=[fach_mathe])
        response = lehrkraft_client.get(
            reverse("archiv:klausur_datei", args=[klausur_haupttermin.pk, "unsinn"])
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestNachschreibmodusUmschalten:
    def test_erfordert_login(self, client):
        response = client.post(reverse("archiv:nachschreibmodus_umschalten"))
        assert response.status_code == 302
        assert reverse("accounts:login_waehlen") in response.url

    def test_erfordert_post(self, lehrkraft_client_factory):
        lehrkraft_client = lehrkraft_client_factory()
        response = lehrkraft_client.get(reverse("archiv:nachschreibmodus_umschalten"))
        assert response.status_code == 405

    def test_schaltet_session_flag_um(self, lehrkraft_client_factory):
        lehrkraft_client = lehrkraft_client_factory()
        assert NACHSCHREIBMODUS_SESSION_KEY not in lehrkraft_client.session

        lehrkraft_client.post(reverse("archiv:nachschreibmodus_umschalten"))
        assert lehrkraft_client.session[NACHSCHREIBMODUS_SESSION_KEY] is True

        lehrkraft_client.post(reverse("archiv:nachschreibmodus_umschalten"))
        assert lehrkraft_client.session[NACHSCHREIBMODUS_SESSION_KEY] is False

    def test_offener_redirect_wird_verhindert(self, lehrkraft_client_factory):
        lehrkraft_client = lehrkraft_client_factory()
        response = lehrkraft_client.post(
            reverse("archiv:nachschreibmodus_umschalten"), {"weiter_zu": "https://evil.example/"}
        )
        assert response.status_code == 302
        assert response.url == reverse("archiv:suche")
