import pytest
from accounts.models import Lehrkraft
from archiv.models import Fach, Klausur
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from importer.models import Importprotokoll
from importer.tests.conftest import klausur_json, manifest_fuer, schreibe_paket_zip


@pytest.fixture
def admin_lehrkraft(db):
    return Lehrkraft.objects.create_user(
        email="admin@schule.de",
        password="s3hrGeheim!",
        status=Lehrkraft.Status.AKTIV,
        ist_admin=True,
    )


@pytest.fixture
def fach_mathe(db):
    return Fach.objects.create(name="Mathematik", kuerzel="M")


def _zip_upload(tmp_path, **kwargs):
    zip_pfad = schreibe_paket_zip(tmp_path / "paket.zip", **kwargs)
    with open(zip_pfad, "rb") as datei:
        return SimpleUploadedFile("paket.zip", datei.read(), content_type="application/zip")


@pytest.mark.django_db
class TestImportHochladen:
    def test_gueltiges_paket_zeigt_vorschau_ohne_fehler(
        self, client, admin_lehrkraft, fach_mathe, tmp_path
    ):
        client.force_login(admin_lehrkraft)
        datei = _zip_upload(
            tmp_path,
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        )

        response = client.post(reverse("adminbereich:import_hochladen"), {"paket": datei})

        assert response.status_code == 200
        assert response.context["vorschau"].hat_fehler is False
        assert client.session.get("import_staging_token")

    def test_ungueltiges_paket_zeigt_formularfehler(self, client, admin_lehrkraft, tmp_path):
        client.force_login(admin_lehrkraft)
        kaputtes_zip = SimpleUploadedFile(
            "kaputt.zip", b"keine-zip-datei", content_type="application/zip"
        )

        response = client.post(reverse("adminbereich:import_hochladen"), {"paket": kaputtes_zip})

        assert response.status_code == 200
        assert response.context["form"].errors


@pytest.mark.django_db
class TestImportBestaetigen:
    def test_nur_post_erlaubt(self, client, admin_lehrkraft):
        client.force_login(admin_lehrkraft)
        response = client.get(reverse("adminbereich:import_bestaetigen"))
        assert response.status_code == 405

    def test_ohne_vorherigen_upload_wird_abgelehnt(self, client, admin_lehrkraft):
        client.force_login(admin_lehrkraft)
        response = client.post(
            reverse("adminbereich:import_bestaetigen"), {"token": "irgendein-token"}
        )
        assert response.status_code == 302
        assert response.url == reverse("adminbereich:import_hochladen")

    def test_erfolgreiche_bestaetigung_importiert_und_protokolliert(
        self, client, admin_lehrkraft, fach_mathe, tmp_path
    ):
        client.force_login(admin_lehrkraft)
        datei = _zip_upload(
            tmp_path,
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        )
        vorschau_response = client.post(reverse("adminbereich:import_hochladen"), {"paket": datei})
        token = vorschau_response.context["token"]

        response = client.post(reverse("adminbereich:import_bestaetigen"), {"token": token})

        assert response.status_code == 302
        assert response.url == reverse("adminbereich:import_protokoll_liste")
        assert Klausur.objects.filter(fach=fach_mathe).count() == 1
        assert Importprotokoll.objects.filter(
            lehrkraft=admin_lehrkraft, ergebnis=Importprotokoll.Ergebnis.ERFOLGREICH
        ).exists()
        assert "import_staging_token" not in client.session

    def test_fehlerhaftes_paket_wird_nicht_importiert(
        self, client, admin_lehrkraft, fach_mathe, tmp_path
    ):
        client.force_login(admin_lehrkraft)
        datei = _zip_upload(
            tmp_path,
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M", themen=["unbekannt.kennung"])],
        )
        vorschau_response = client.post(reverse("adminbereich:import_hochladen"), {"paket": datei})
        token = vorschau_response.context["token"]

        response = client.post(reverse("adminbereich:import_bestaetigen"), {"token": token})

        assert response.status_code == 302
        assert Klausur.objects.filter(fach=fach_mathe).count() == 0
