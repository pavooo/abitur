import datetime

import pytest
from accounts.models import Lehrkraft, Zugangscode
from archiv.models import Fach
from django.urls import reverse
from django.utils import timezone


@pytest.fixture
def admin_client(client, db):
    admin = Lehrkraft.objects.create_user(
        email="admin@schule.de",
        password="s3hrGeheim!",
        status=Lehrkraft.Status.AKTIV,
        ist_admin=True,
    )
    client.force_login(admin)
    return client


@pytest.fixture
def fach(db):
    fach, _erstellt = Fach.objects.get_or_create(kuerzel="M", defaults={"name": "Mathematik"})
    return fach


@pytest.mark.django_db
class TestLehrkraftVerwaltung:
    def test_freischalten_setzt_status_aktiv(self, admin_client):
        lehrkraft = Lehrkraft.objects.create_user(email="neu@schule.de", password="s3hrGeheim!")

        admin_client.post(
            reverse("adminbereich:lehrkraft_detail", args=[lehrkraft.pk]),
            {"aktion": "freischalten"},
        )

        lehrkraft.refresh_from_db()
        assert lehrkraft.status == Lehrkraft.Status.AKTIV

    def test_sperren_setzt_status_gesperrt(self, admin_client):
        lehrkraft = Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )

        admin_client.post(
            reverse("adminbereich:lehrkraft_detail", args=[lehrkraft.pk]),
            {"aktion": "sperren"},
        )

        lehrkraft.refresh_from_db()
        assert lehrkraft.status == Lehrkraft.Status.GESPERRT

    def test_admin_recht_umschalten(self, admin_client):
        lehrkraft = Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )

        admin_client.post(
            reverse("adminbereich:lehrkraft_detail", args=[lehrkraft.pk]),
            {"aktion": "admin_umschalten"},
        )
        lehrkraft.refresh_from_db()
        assert lehrkraft.ist_admin is True

        admin_client.post(
            reverse("adminbereich:lehrkraft_detail", args=[lehrkraft.pk]),
            {"aktion": "admin_umschalten"},
        )
        lehrkraft.refresh_from_db()
        assert lehrkraft.ist_admin is False

    def test_faecher_zuordnen(self, admin_client, fach):
        lehrkraft = Lehrkraft.objects.create_user(
            email="aktiv@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )

        admin_client.post(
            reverse("adminbereich:lehrkraft_detail", args=[lehrkraft.pk]),
            {"aktion": "faecher_speichern", "faecher": [fach.pk]},
        )

        lehrkraft.refresh_from_db()
        assert list(lehrkraft.faecher.all()) == [fach]


@pytest.mark.django_db
class TestFachAnlegen:
    def test_fach_anlegen(self, admin_client):
        # Bewusst kein Standardfach aus Migration 0007 (die bereits existieren
        # und hier eine Validierungsfehler statt eines Redirects auslösen würden).
        response = admin_client.post(
            reverse("adminbereich:fach_liste"),
            {"name": "Niederländisch", "kuerzel": "NL"},
        )

        assert response.status_code == 302
        assert Fach.objects.filter(kuerzel="NL").exists()


@pytest.mark.django_db
class TestZugangscodeVerwaltung:
    def test_zugangscode_erstellen_zeigt_klartext_einmalig(self, admin_client, fach):
        response = admin_client.post(
            reverse("adminbereich:zugangscode_liste"),
            {
                "fach": fach.pk,
                "bezeichnung": "Mathe-LK Abi 2027",
                "ablaufdatum": (timezone.localdate() + datetime.timedelta(days=30)).isoformat(),
            },
            follow=True,
        )

        assert Zugangscode.objects.filter(bezeichnung="Mathe-LK Abi 2027").exists()
        messages = [str(message) for message in response.context["messages"]]
        assert any("Zugangscode erstellt" in message for message in messages)

    def test_sperren_umschalten(self, admin_client, fach):
        zugangscode, _klartext = Zugangscode.erstellen(
            fach=fach,
            bezeichnung="Mathe-LK Abi 2027",
            ablaufdatum=timezone.localdate() + datetime.timedelta(days=30),
        )

        admin_client.post(
            reverse("adminbereich:zugangscode_sperren_umschalten", args=[zugangscode.pk])
        )
        zugangscode.refresh_from_db()
        assert zugangscode.gesperrt is True

        admin_client.post(
            reverse("adminbereich:zugangscode_sperren_umschalten", args=[zugangscode.pk])
        )
        zugangscode.refresh_from_db()
        assert zugangscode.gesperrt is False
