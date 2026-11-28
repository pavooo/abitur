import pymupdf
import pytest
from accounts.models import Lehrkraft
from archiv.models import Aufgabe, Bereich, Fach, Klausur
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse


def _echtes_pdf(seiten=2) -> bytes:
    dokument = pymupdf.open()
    for _ in range(seiten):
        dokument.new_page()
    daten = dokument.tobytes()
    dokument.close()
    return daten


def _pdf_upload():
    return SimpleUploadedFile("klausur.pdf", _echtes_pdf(), content_type="application/pdf")


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
def klausur(fach, lehrkraft_client):
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


def _erstelle_aufgabe(klausur, nummer=1):
    return Aufgabe.objects.create(
        klausur=klausur, nummer=nummer, pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN
    )


@pytest.mark.django_db
class TestBereichModell:
    def test_erfordert_genau_ein_ziel(self, klausur):
        aufgabe = _erstelle_aufgabe(klausur)

        with pytest.raises(IntegrityError), transaction.atomic():
            Bereich.objects.create(aufgabe=None, teilaufgabe=None, seite=1, x0=0, y0=0, x1=1, y1=1)

        # Gültig mit genau einem Ziel.
        Bereich.objects.create(aufgabe=aufgabe, seite=1, x0=0, y0=0, x1=1, y1=1)


@pytest.mark.django_db
class TestAufgabeErstellenUndLoeschen:
    def test_erstellt_aufgabe(self, lehrkraft_client, klausur):
        response = lehrkraft_client.post(
            reverse("editor:aufgabe_erstellen", args=[klausur.pk]),
            {
                "nummer": 1,
                "kontext": "Bakterienwachstum",
                "pruefungsteil": Aufgabe.Pruefungsteil.MIT_HILFSMITTELN,
                "aufgabenbereich": Aufgabe.Aufgabenbereich.PFLICHT,
            },
        )

        assert response.status_code == 200
        aufgabe = Aufgabe.objects.get(klausur=klausur, nummer=1)
        assert aufgabe.kontext == "Bakterienwachstum"

    def test_doppelte_nummer_schlaegt_fehl(self, lehrkraft_client, klausur):
        _erstelle_aufgabe(klausur, nummer=1)

        response = lehrkraft_client.post(
            reverse("editor:aufgabe_erstellen", args=[klausur.pk]),
            {
                "nummer": 1,
                "pruefungsteil": Aufgabe.Pruefungsteil.MIT_HILFSMITTELN,
                "aufgabenbereich": Aufgabe.Aufgabenbereich.PFLICHT,
            },
        )

        assert response.status_code == 200
        assert Aufgabe.objects.filter(klausur=klausur).count() == 1

    def test_loescht_aufgabe(self, lehrkraft_client, klausur):
        aufgabe = _erstelle_aufgabe(klausur)

        response = lehrkraft_client.post(
            reverse("editor:aufgabe_loeschen", args=[klausur.pk, aufgabe.pk])
        )

        assert response.status_code == 200
        assert not Aufgabe.objects.filter(pk=aufgabe.pk).exists()

    def test_fremde_aufgabe_kann_nicht_geloescht_werden(self, lehrkraft_client, fach):
        andere_lehrkraft = Lehrkraft.objects.create_user(
            email="andere@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        andere_klausur = Klausur.objects.create(
            fach=fach,
            jahr=2025,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="fremd",
            titel="Fremd",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=_pdf_upload(),
            status=Klausur.Status.ENTWURF,
            ersteller=andere_lehrkraft,
        )
        aufgabe = _erstelle_aufgabe(andere_klausur)

        response = lehrkraft_client.post(
            reverse("editor:aufgabe_loeschen", args=[andere_klausur.pk, aufgabe.pk])
        )

        assert response.status_code == 404
        assert Aufgabe.objects.filter(pk=aufgabe.pk).exists()


@pytest.mark.django_db
class TestBereichErstellenAktualisierenLoeschen:
    def test_erstellt_bereich_und_leitet_seitenbereich_ab(self, lehrkraft_client, klausur):
        aufgabe = _erstelle_aufgabe(klausur)

        response = lehrkraft_client.post(
            reverse("editor:bereich_erstellen", args=[klausur.pk]),
            {"aufgabe": aufgabe.pk, "seite": 2, "x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.6},
        )

        assert response.status_code == 200
        daten = response.json()
        assert daten["seite"] == 2
        assert daten["aufgabe"] == aufgabe.pk

        aufgabe.refresh_from_db()
        assert aufgabe.seite_von == 2
        assert aufgabe.seite_bis == 2

    def test_mehrere_bereiche_ueber_mehrere_seiten_ergeben_seitenspanne(
        self, lehrkraft_client, klausur
    ):
        aufgabe = _erstelle_aufgabe(klausur)
        Bereich.objects.create(aufgabe=aufgabe, seite=1, x0=0, y0=0, x1=1, y1=1)

        lehrkraft_client.post(
            reverse("editor:bereich_erstellen", args=[klausur.pk]),
            {"aufgabe": aufgabe.pk, "seite": 2, "x0": 0, "y0": 0, "x1": 1, "y1": 1},
        )

        aufgabe.refresh_from_db()
        assert aufgabe.seite_von == 1
        assert aufgabe.seite_bis == 2

    def test_aktualisiert_koordinaten(self, lehrkraft_client, klausur):
        aufgabe = _erstelle_aufgabe(klausur)
        bereich = Bereich.objects.create(aufgabe=aufgabe, seite=1, x0=0, y0=0, x1=0.5, y1=0.5)

        response = lehrkraft_client.post(
            reverse("editor:bereich_aktualisieren", args=[klausur.pk, bereich.pk]),
            {"x0": 0.1, "y0": 0.1, "x1": 0.9, "y1": 0.9},
        )

        assert response.status_code == 200
        bereich.refresh_from_db()
        assert bereich.x0 == 0.1
        assert bereich.x1 == 0.9

    def test_loescht_bereich_und_aktualisiert_seitenbereich(self, lehrkraft_client, klausur):
        aufgabe = _erstelle_aufgabe(klausur)
        bereich_1 = Bereich.objects.create(aufgabe=aufgabe, seite=1, x0=0, y0=0, x1=1, y1=1)
        bereich_2 = Bereich.objects.create(aufgabe=aufgabe, seite=2, x0=0, y0=0, x1=1, y1=1)

        response = lehrkraft_client.post(
            reverse("editor:bereich_loeschen", args=[klausur.pk, bereich_2.pk])
        )

        assert response.status_code == 200
        assert not Bereich.objects.filter(pk=bereich_2.pk).exists()
        aufgabe.refresh_from_db()
        assert aufgabe.seite_von == 1
        assert aufgabe.seite_bis == 1

        lehrkraft_client.post(reverse("editor:bereich_loeschen", args=[klausur.pk, bereich_1.pk]))
        aufgabe.refresh_from_db()
        assert aufgabe.seite_von is None
        assert aufgabe.seite_bis is None

    def test_bereich_fremder_klausur_liefert_404(self, lehrkraft_client, klausur, fach):
        andere_lehrkraft = Lehrkraft.objects.create_user(
            email="andere2@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        andere_klausur = Klausur.objects.create(
            fach=fach,
            jahr=2025,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="fremd2",
            titel="Fremd",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=_pdf_upload(),
            status=Klausur.Status.ENTWURF,
            ersteller=andere_lehrkraft,
        )
        fremde_aufgabe = _erstelle_aufgabe(andere_klausur)
        fremder_bereich = Bereich.objects.create(
            aufgabe=fremde_aufgabe, seite=1, x0=0, y0=0, x1=1, y1=1
        )

        response = lehrkraft_client.post(
            reverse("editor:bereich_aktualisieren", args=[klausur.pk, fremder_bereich.pk]),
            {"x0": 0, "y0": 0, "x1": 1, "y1": 1},
        )

        assert response.status_code == 404
