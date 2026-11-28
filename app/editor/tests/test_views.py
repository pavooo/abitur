import pytest
from accounts.models import Lehrkraft
from archiv.models import Fach, Klausur
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


def dummy_pdf(name="klausur.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 Dummy", content_type="application/pdf")


@pytest.fixture
def fach(db):
    fach, _erstellt = Fach.objects.get_or_create(kuerzel="M", defaults={"name": "Mathematik"})
    return fach


def erstelle_klausur(fach, ersteller, status, variante=""):
    return Klausur.objects.create(
        fach=fach,
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        variante=variante,
        titel="Analysis",
        hilfsmittel=Klausur.Hilfsmittel.TR,
        pdf=dummy_pdf(f"{status}-{variante}.pdf"),
        status=status,
        ersteller=ersteller,
    )


@pytest.mark.django_db
class TestMeineKlausuren:
    def test_anonym_wird_zum_login_umgeleitet(self, client):
        response = client.get(reverse("editor:meine_klausuren"))
        assert response.status_code == 302
        assert reverse("accounts:login_waehlen") in response.url

    def test_zeigt_nur_eigene_klausuren(self, client, fach):
        lehrkraft_a = Lehrkraft.objects.create_user(
            email="a@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        lehrkraft_b = Lehrkraft.objects.create_user(
            email="b@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        eigene = erstelle_klausur(fach, lehrkraft_a, Klausur.Status.ENTWURF, variante="eigene")
        fremde = erstelle_klausur(fach, lehrkraft_b, Klausur.Status.ENTWURF, variante="fremde")

        client.force_login(lehrkraft_a)
        response = client.get(reverse("editor:meine_klausuren"))

        klausuren = [eintrag["klausur"] for eintrag in response.context["eintraege"]]
        assert eigene in klausuren
        assert fremde not in klausuren

    def test_zeigt_ablehnungskommentar(self, client, fach):
        lehrkraft = Lehrkraft.objects.create_user(
            email="a@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        klausur = erstelle_klausur(fach, lehrkraft, Klausur.Status.ABGELEHNT, variante="x")
        klausur.ablehnungskommentar = "Termin fehlt."
        klausur.save(update_fields=["ablehnungskommentar"])

        client.force_login(lehrkraft)
        response = client.get(reverse("editor:meine_klausuren"))

        assert "Termin fehlt." in response.content.decode()
