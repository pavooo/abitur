import pytest
from accounts.models import Lehrkraft
from django.urls import reverse


@pytest.fixture
def admin_lehrkraft(db):
    return Lehrkraft.objects.create_user(
        email="admin@schule.de",
        password="s3hrGeheim!",
        status=Lehrkraft.Status.AKTIV,
        ist_admin=True,
    )


@pytest.fixture
def normale_lehrkraft(db):
    return Lehrkraft.objects.create_user(
        email="lehrkraft@schule.de",
        password="s3hrGeheim!",
        status=Lehrkraft.Status.AKTIV,
    )


ADMIN_URLS = [
    "adminbereich:dashboard",
    "adminbereich:lehrkraft_liste",
    "adminbereich:fach_liste",
    "adminbereich:zugangscode_liste",
    "adminbereich:import_hochladen",
    "adminbereich:import_protokoll_liste",
    "adminbereich:nachschreib_protokoll_liste",
]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ADMIN_URLS)
class TestAdminbereichRechte:
    def test_anonym_wird_zum_login_umgeleitet(self, client, url_name):
        response = client.get(reverse(url_name))
        assert response.status_code == 302
        assert reverse("accounts:login_waehlen") in response.url

    def test_lehrkraft_ohne_admin_recht_wird_abgelehnt(self, client, normale_lehrkraft, url_name):
        client.force_login(normale_lehrkraft)
        response = client.get(reverse(url_name))
        assert response.status_code == 403

    def test_admin_lehrkraft_hat_zugriff(self, client, admin_lehrkraft, url_name):
        client.force_login(admin_lehrkraft)
        response = client.get(reverse(url_name))
        assert response.status_code == 200


@pytest.mark.django_db
class TestLehrkraftDetailRechte:
    def test_lehrkraft_ohne_admin_recht_wird_abgelehnt(self, client, normale_lehrkraft):
        client.force_login(normale_lehrkraft)
        response = client.get(reverse("adminbereich:lehrkraft_detail", args=[normale_lehrkraft.pk]))
        assert response.status_code == 403

    def test_admin_lehrkraft_hat_zugriff(self, client, admin_lehrkraft, normale_lehrkraft):
        client.force_login(admin_lehrkraft)
        response = client.get(reverse("adminbereich:lehrkraft_detail", args=[normale_lehrkraft.pk]))
        assert response.status_code == 200
