import pytest
from accounts.models import Lehrkraft
from archiv.models import Fach, Klausur, NachschreibZugriff
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


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


@pytest.mark.django_db
class TestNachschreibProtokollListe:
    def test_listet_protokollierte_zugriffe(self, admin_client):
        fach, _erstellt = Fach.objects.get_or_create(kuerzel="M", defaults={"name": "Mathematik"})
        klausur = Klausur.objects.create(
            fach=fach,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.NACHSCHREIBTERMIN,
            titel="Analysis (Nachschreiber)",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=SimpleUploadedFile("nachschreiber.pdf", b"%PDF-1.4 Dummy"),
        )
        lehrkraft = Lehrkraft.objects.create_user(
            email="lehrkraft@schule.de", password="s3hrGeheim!"
        )
        NachschreibZugriff.objects.create(lehrkraft=lehrkraft, klausur=klausur)

        response = admin_client.get(reverse("adminbereich:nachschreib_protokoll_liste"))

        assert response.status_code == 200
        assert list(response.context["zugriffe"]) == list(
            NachschreibZugriff.objects.filter(klausur=klausur)
        )
        assert lehrkraft.email.encode() in response.content

    def test_leere_liste_zeigt_hinweis(self, admin_client):
        response = admin_client.get(reverse("adminbereich:nachschreib_protokoll_liste"))
        assert response.status_code == 200
        assert b"Noch keine Zugriffe" in response.content
