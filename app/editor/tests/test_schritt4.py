import pymupdf
import pytest
from accounts.models import Lehrkraft
from archiv.models import Aufgabe, Fach, Klausur, Teilaufgabe
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


def _pdf_upload():
    dokument = pymupdf.open()
    dokument.new_page()
    daten = dokument.tobytes()
    dokument.close()
    return SimpleUploadedFile("klausur.pdf", daten, content_type="application/pdf")


@pytest.fixture
def fach(db):
    fach, _erstellt = Fach.objects.get_or_create(kuerzel="M", defaults={"name": "Mathematik"})
    return fach


@pytest.fixture
def lehrkraft_client(client, db, fach):
    lehrkraft = Lehrkraft.objects.create_user(
        email="lehrkraft@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
    )
    lehrkraft.faecher.set([fach])
    client.force_login(lehrkraft)
    client.lehrkraft = lehrkraft
    return client


@pytest.fixture
def unvollstaendige_klausur(fach, lehrkraft_client):
    return Klausur.objects.create(
        fach=fach,
        jahr=2025,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        titel="Analysis",
        hilfsmittel=Klausur.Hilfsmittel.TR,
        pdf=_pdf_upload(),
        status=Klausur.Status.ENTWURF,
        ersteller=lehrkraft_client.lehrkraft,
    )


@pytest.fixture
def vollstaendige_klausur(unvollstaendige_klausur):
    from archiv.models import Bereich

    aufgabe = Aufgabe.objects.create(
        klausur=unvollstaendige_klausur,
        nummer=1,
        seite_von=1,
        seite_bis=1,
        pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN,
    )
    Bereich.objects.create(aufgabe=aufgabe, seite=1, x0=0, y0=0, x1=1, y1=1)
    teilaufgabe = Teilaufgabe.objects.create(
        aufgabe=aufgabe,
        bezeichnung="1a",
        seite=1,
        text="Text",
        anforderungsbereich=Teilaufgabe.Anforderungsbereich.I,
    )
    Bereich.objects.create(teilaufgabe=teilaufgabe, seite=1, x0=0, y0=0, x1=1, y1=1)
    return unvollstaendige_klausur


@pytest.mark.django_db
class TestSchritt4:
    def test_zeigt_luecken(self, lehrkraft_client, unvollstaendige_klausur):
        response = lehrkraft_client.get(
            reverse("editor:schritt4", args=[unvollstaendige_klausur.pk])
        )

        assert response.status_code == 200
        assert "Noch nicht vollständig" in response.content.decode()

    def test_seite_ohne_bereich_zeigt_weiterhin_luecke(
        self, lehrkraft_client, unvollstaendige_klausur
    ):
        """Regression: Option C setzt `seite`/`seite_von`/`seite_bis` direkt aus dem
        JSON, ohne einen Bereich anzulegen – das darf Schritt 4 nicht als erledigt
        durchgehen lassen (CLAUDE.md, Abschnitt Option C)."""
        aufgabe = Aufgabe.objects.create(
            klausur=unvollstaendige_klausur,
            nummer=1,
            seite_von=1,
            seite_bis=1,
            pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN,
        )
        Teilaufgabe.objects.create(
            aufgabe=aufgabe,
            bezeichnung="1a",
            seite=1,
            text="Text",
            anforderungsbereich=Teilaufgabe.Anforderungsbereich.I,
        )

        response = lehrkraft_client.get(
            reverse("editor:schritt4", args=[unvollstaendige_klausur.pk])
        )

        inhalt = response.content.decode()
        assert "Noch nicht vollständig" in inhalt
        assert "kein Bereich markiert" in inhalt

    def test_einreichen_mit_luecken_schlaegt_fehl(self, lehrkraft_client, unvollstaendige_klausur):
        response = lehrkraft_client.post(
            reverse("editor:schritt4", args=[unvollstaendige_klausur.pk]), follow=True
        )

        unvollstaendige_klausur.refresh_from_db()
        assert unvollstaendige_klausur.status == Klausur.Status.ENTWURF
        assert response.status_code == 200

    def test_einreichen_vollstaendiger_klausur_setzt_status(
        self, lehrkraft_client, vollstaendige_klausur
    ):
        response = lehrkraft_client.post(
            reverse("editor:schritt4", args=[vollstaendige_klausur.pk])
        )

        vollstaendige_klausur.refresh_from_db()
        assert vollstaendige_klausur.status == Klausur.Status.EINGEREICHT
        assert response.status_code == 302

    def test_eingereichte_klausur_kann_nicht_mehr_bearbeitet_werden(
        self, lehrkraft_client, vollstaendige_klausur
    ):
        lehrkraft_client.post(reverse("editor:schritt4", args=[vollstaendige_klausur.pk]))

        response = lehrkraft_client.get(reverse("editor:schritt1", args=[vollstaendige_klausur.pk]))

        assert response.status_code == 404
