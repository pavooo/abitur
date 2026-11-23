import datetime

import pytest
from archiv.models import Fach
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Lehrkraft, Zugangscode


@pytest.fixture
def fach(db):
    fach, _erstellt = Fach.objects.get_or_create(kuerzel="M", defaults={"name": "Mathematik"})
    return fach


@pytest.fixture
def gueltiger_code(fach):
    zugangscode, klartext_code = Zugangscode.erstellen(
        fach=fach,
        bezeichnung="Mathe-LK Abi 2027",
        ablaufdatum=timezone.localdate() + datetime.timedelta(days=30),
    )
    return zugangscode, klartext_code


@pytest.mark.django_db
class TestLehrkraftLogin:
    def test_ausstehende_lehrkraft_kann_sich_nicht_anmelden(self, client):
        Lehrkraft.objects.create_user(email="neu@schule.de", password="s3hrGeheim!")

        response = client.post(
            reverse("accounts:lehrkraft_login"),
            {"username": "neu@schule.de", "password": "s3hrGeheim!"},
        )

        assert response.status_code == 200
        assert "Freischaltung" in response.content.decode()
        assert not response.wsgi_request.user.is_authenticated

    def test_gesperrte_lehrkraft_kann_sich_nicht_anmelden(self, client):
        Lehrkraft.objects.create_user(
            email="gesperrt@schule.de",
            password="s3hrGeheim!",
            status=Lehrkraft.Status.GESPERRT,
        )

        response = client.post(
            reverse("accounts:lehrkraft_login"),
            {"username": "gesperrt@schule.de", "password": "s3hrGeheim!"},
        )

        assert response.status_code == 200
        assert "gesperrt" in response.content.decode()

    def test_aktive_lehrkraft_wird_zur_startseite_weitergeleitet(self, client):
        Lehrkraft.objects.create_user(
            email="aktiv@schule.de",
            password="s3hrGeheim!",
            status=Lehrkraft.Status.AKTIV,
        )

        response = client.post(
            reverse("accounts:lehrkraft_login"),
            {"username": "aktiv@schule.de", "password": "s3hrGeheim!"},
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:lehrkraft_startseite")

    def test_admin_lehrkraft_wird_zum_adminbereich_weitergeleitet(self, client):
        Lehrkraft.objects.create_user(
            email="admin@schule.de",
            password="s3hrGeheim!",
            status=Lehrkraft.Status.AKTIV,
            ist_admin=True,
        )

        response = client.post(
            reverse("accounts:lehrkraft_login"),
            {"username": "admin@schule.de", "password": "s3hrGeheim!"},
        )

        assert response.status_code == 302
        assert response.url == reverse("adminbereich:dashboard")

    def test_zu_viele_fehlversuche_sperren_den_login(self, client):
        Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )

        for _ in range(settings.AXES_FAILURE_LIMIT):
            client.post(
                reverse("accounts:lehrkraft_login"),
                {"username": "aktiv@schule.de", "password": "falsches-passwort"},
            )

        response = client.post(
            reverse("accounts:lehrkraft_login"),
            {"username": "aktiv@schule.de", "password": "s3hrGeheim!"},
        )

        assert response.status_code == 429

    def test_login_beendet_bestehende_sus_session(self, client, gueltiger_code):
        _zugangscode, klartext_code = gueltiger_code
        client.post(reverse("accounts:code_login"), {"code": klartext_code})
        assert "sus_zugangscode_id" in client.session

        Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        client.post(
            reverse("accounts:lehrkraft_login"),
            {"username": "aktiv@schule.de", "password": "s3hrGeheim!"},
        )

        assert "sus_zugangscode_id" not in client.session


@pytest.mark.django_db
class TestRegistrierung:
    def test_erste_registrierung_wird_automatisch_admin(self, client):
        response = client.post(
            reverse("accounts:registrieren"),
            {
                "email": "erster@schule.de",
                "vorname": "Erste",
                "nachname": "Lehrkraft",
                "passwort": "s3hrGeheimesPasswort!",
                "passwort_wiederholen": "s3hrGeheimesPasswort!",
            },
        )

        assert response.status_code == 302
        lehrkraft = Lehrkraft.objects.get(email="erster@schule.de")
        assert lehrkraft.status == Lehrkraft.Status.AKTIV
        assert lehrkraft.ist_admin is True

    def test_zweite_registrierung_bleibt_ausstehend(self, client):
        Lehrkraft.objects.create_user(
            email="erster@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )

        client.post(
            reverse("accounts:registrieren"),
            {
                "email": "zweite@schule.de",
                "vorname": "Zweite",
                "nachname": "Lehrkraft",
                "passwort": "s3hrGeheimesPasswort!",
                "passwort_wiederholen": "s3hrGeheimesPasswort!",
            },
        )

        lehrkraft = Lehrkraft.objects.get(email="zweite@schule.de")
        assert lehrkraft.status == Lehrkraft.Status.AUSSTEHEND
        assert lehrkraft.ist_admin is False

    def test_passwoerter_muessen_uebereinstimmen(self, client):
        response = client.post(
            reverse("accounts:registrieren"),
            {
                "email": "neu@schule.de",
                "vorname": "Neu",
                "nachname": "Lehrkraft",
                "passwort": "s3hrGeheimesPasswort!",
                "passwort_wiederholen": "anderesPasswort!",
            },
        )

        assert response.status_code == 200
        assert not Lehrkraft.objects.filter(email="neu@schule.de").exists()


@pytest.mark.django_db
class TestZugangscodeLogin:
    def test_gueltiger_code_meldet_an(self, client, gueltiger_code):
        _zugangscode, klartext_code = gueltiger_code

        response = client.post(reverse("accounts:code_login"), {"code": klartext_code})

        assert response.status_code == 302
        assert response.url == reverse("accounts:sus_startseite")
        assert "sus_zugangscode_id" in client.session

    def test_ungueltiger_code_wird_abgelehnt(self, client, fach):
        response = client.post(reverse("accounts:code_login"), {"code": "existiert-nicht"})

        assert response.status_code == 200
        assert "sus_zugangscode_id" not in client.session

    def test_abgelaufener_code_wird_abgelehnt(self, client, fach):
        _zugangscode, klartext_code = Zugangscode.erstellen(
            fach=fach,
            bezeichnung="Alt",
            ablaufdatum=timezone.localdate() - datetime.timedelta(days=1),
        )

        response = client.post(reverse("accounts:code_login"), {"code": klartext_code})

        assert response.status_code == 200
        assert "sus_zugangscode_id" not in client.session

    def test_zu_viele_fehlversuche_werden_gesperrt(self, client, fach):
        for _ in range(settings.AXES_FAILURE_LIMIT):
            client.post(reverse("accounts:code_login"), {"code": "falscher-code"})

        response = client.post(reverse("accounts:code_login"), {"code": "falscher-code"})

        assert "Zu viele Fehlversuche" in response.content.decode()

    def test_code_login_beendet_bestehende_lehrkraft_session(self, client, gueltiger_code):
        _zugangscode, klartext_code = gueltiger_code
        Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        client.post(
            reverse("accounts:lehrkraft_login"),
            {"username": "aktiv@schule.de", "password": "s3hrGeheim!"},
        )

        client.post(reverse("accounts:code_login"), {"code": klartext_code})

        response = client.get(reverse("accounts:sus_startseite"))
        assert response.status_code == 200
        assert not response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
class TestLehrkraftSessionMiddleware:
    def test_session_endet_wenn_lehrkraft_nachtraeglich_gesperrt_wird(self, client):
        lehrkraft = Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        client.force_login(lehrkraft)

        lehrkraft.status = Lehrkraft.Status.GESPERRT
        lehrkraft.save()

        response = client.get(reverse("accounts:lehrkraft_startseite"))
        assert response.status_code == 302
        assert not response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
class TestSusSessionMiddleware:
    def test_session_endet_wenn_code_nachtraeglich_gesperrt_wird(self, client, gueltiger_code):
        zugangscode, klartext_code = gueltiger_code
        client.post(reverse("accounts:code_login"), {"code": klartext_code})
        assert "sus_zugangscode_id" in client.session

        zugangscode.gesperrt = True
        zugangscode.save()

        client.get(reverse("accounts:sus_startseite"))
        assert "sus_zugangscode_id" not in client.session

    def test_zugriff_auf_sus_startseite_ohne_session_leitet_weiter(self, client):
        response = client.get(reverse("accounts:sus_startseite"))
        assert response.status_code == 302
        assert response.url == reverse("accounts:login_waehlen")


@pytest.mark.django_db
class TestLogout:
    def test_logout_per_post_meldet_ab(self, client):
        lehrkraft = Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        client.force_login(lehrkraft)

        response = client.post(reverse("accounts:logout"))

        assert response.status_code == 302
        assert not response.wsgi_request.user.is_authenticated

    def test_logout_per_get_ist_nicht_erlaubt(self, client):
        # LogoutView akzeptiert seit Django 4.1 nur noch POST (CSRF-Schutz) –
        # das base.html-Template muss daher ein Formular statt eines <a href>
        # verwenden, sonst gibt es hier einen 405 (siehe Vorfall).
        lehrkraft = Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        client.force_login(lehrkraft)

        response = client.get(reverse("accounts:logout"))

        assert response.status_code == 405
