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


@pytest.fixture
def andere_lehrkraft(db, fach):
    lehrkraft = Lehrkraft.objects.create_user(
        email="lehrkraft@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
    )
    lehrkraft.faecher.set([fach])
    return lehrkraft


@pytest.fixture
def admin_client(client, db, fach):
    admin = Lehrkraft.objects.create_user(
        email="admin@schule.de",
        password="s3hrGeheim!",
        status=Lehrkraft.Status.AKTIV,
        ist_admin=True,
    )
    admin.faecher.set([fach])
    client.force_login(admin)
    return client


def erstelle_eingereichte_klausur(fach, ersteller, variante=""):
    return Klausur.objects.create(
        fach=fach,
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        variante=variante,
        titel="Analysis",
        hilfsmittel=Klausur.Hilfsmittel.TR,
        pdf=dummy_pdf(f"eingereicht-{variante}.pdf"),
        status=Klausur.Status.EINGEREICHT,
        ersteller=ersteller,
    )


@pytest.mark.django_db
class TestFreigabeListe:
    def test_zeigt_nur_eingereichte_klausuren(self, admin_client, fach, andere_lehrkraft):
        eingereicht = erstelle_eingereichte_klausur(fach, andere_lehrkraft, variante="a")
        entwurf = Klausur.objects.create(
            fach=fach,
            jahr=2024,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="entwurf",
            titel="Noch nicht fertig",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=dummy_pdf("entwurf.pdf"),
            status=Klausur.Status.ENTWURF,
            ersteller=andere_lehrkraft,
        )

        response = admin_client.get(reverse("adminbereich:freigabe_liste"))

        klausuren = list(response.context["klausuren"])
        assert eingereicht in klausuren
        assert entwurf not in klausuren


@pytest.mark.django_db
class TestFreigabeDetail:
    def test_zeigt_freigeben_und_ablehnen_bei_eingereichter_klausur(
        self, admin_client, fach, andere_lehrkraft
    ):
        klausur = erstelle_eingereichte_klausur(fach, andere_lehrkraft, variante="anzeigen")

        response = admin_client.get(reverse("adminbereich:freigabe_detail", args=[klausur.pk]))

        assert response.status_code == 200
        inhalt = response.content.decode()
        assert "Freigeben" in inhalt
        assert "Ablehnen" in inhalt

    def test_freigeben_setzt_status_freigegeben(self, admin_client, fach, andere_lehrkraft):
        klausur = erstelle_eingereichte_klausur(fach, andere_lehrkraft, variante="freigeben")

        admin_client.post(
            reverse("adminbereich:freigabe_detail", args=[klausur.pk]), {"aktion": "freigeben"}
        )

        klausur.refresh_from_db()
        assert klausur.status == Klausur.Status.FREIGEGEBEN

    def test_ablehnen_erfordert_kommentar(self, admin_client, fach, andere_lehrkraft):
        klausur = erstelle_eingereichte_klausur(fach, andere_lehrkraft, variante="ablehnen-leer")

        admin_client.post(
            reverse("adminbereich:freigabe_detail", args=[klausur.pk]),
            {"aktion": "ablehnen", "kommentar": ""},
        )

        klausur.refresh_from_db()
        assert klausur.status == Klausur.Status.EINGEREICHT

    def test_ablehnen_mit_kommentar_setzt_status_und_kommentar(
        self, admin_client, fach, andere_lehrkraft
    ):
        klausur = erstelle_eingereichte_klausur(fach, andere_lehrkraft, variante="ablehnen")

        admin_client.post(
            reverse("adminbereich:freigabe_detail", args=[klausur.pk]),
            {"aktion": "ablehnen", "kommentar": "Termin fehlt."},
        )

        klausur.refresh_from_db()
        assert klausur.status == Klausur.Status.ABGELEHNT
        assert klausur.ablehnungskommentar == "Termin fehlt."

    def test_admin_kann_nicht_fachfremde_klausur_freigeben(self, admin_client, db):
        anderes_fach, _ = Fach.objects.get_or_create(kuerzel="D", defaults={"name": "Deutsch"})
        fachfremde_lehrkraft = Lehrkraft.objects.create_user(
            email="deutsch@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        fachfremde_lehrkraft.faecher.set([anderes_fach])
        klausur = erstelle_eingereichte_klausur(anderes_fach, fachfremde_lehrkraft, variante="x")

        response = admin_client.get(reverse("adminbereich:freigabe_detail", args=[klausur.pk]))

        assert response.status_code == 404

    def test_bereits_freigegebene_klausur_kann_nicht_erneut_freigegeben_werden(
        self, admin_client, fach, andere_lehrkraft
    ):
        klausur = erstelle_eingereichte_klausur(fach, andere_lehrkraft, variante="schon-fertig")
        klausur.status = Klausur.Status.FREIGEGEBEN
        klausur.save(update_fields=["status"])

        response = admin_client.post(
            reverse("adminbereich:freigabe_detail", args=[klausur.pk]),
            {"aktion": "freigeben"},
            follow=True,
        )

        assert response.redirect_chain
        klausur.refresh_from_db()
        assert klausur.status == Klausur.Status.FREIGEGEBEN
