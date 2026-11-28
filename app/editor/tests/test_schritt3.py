import pymupdf
import pytest
from accounts.models import Lehrkraft
from archiv.models import Aufgabe, Fach, Klausur, Teilaufgabe, Thema
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


def _pdf_mit_text(text="Ermitteln Sie die Nullstellen. Begründen Sie Ihr Ergebnis.") -> bytes:
    dokument = pymupdf.open()
    seite = dokument.new_page()
    seite.insert_text((72, 100), text, fontsize=14)
    daten = dokument.tobytes()
    dokument.close()
    return daten


def _pdf_upload():
    return SimpleUploadedFile("klausur.pdf", _pdf_mit_text(), content_type="application/pdf")


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


@pytest.fixture
def aufgabe(klausur):
    return Aufgabe.objects.create(
        klausur=klausur, nummer=1, pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN
    )


@pytest.fixture
def thema_nullstellen(fach):
    return Thema.objects.create(fach=fach, kennung="analysis.fkt.nullstellen", name="Nullstellen")


@pytest.mark.django_db
class TestSchritt3Ansicht:
    def test_ohne_aufgaben_zeigt_hinweis(self, lehrkraft_client, klausur):
        response = lehrkraft_client.get(reverse("editor:schritt3", args=[klausur.pk]))

        assert response.status_code == 200
        assert "Noch keine Aufgaben angelegt" in response.content.decode()

    def test_mit_aufgabe_zeigt_panel(self, lehrkraft_client, klausur, aufgabe):
        response = lehrkraft_client.get(reverse("editor:schritt3", args=[klausur.pk]))

        assert response.status_code == 200
        assert f"Aufgabe {aufgabe.nummer}" in response.content.decode()


@pytest.mark.django_db
class TestTeilaufgabeErstellenUndLoeschen:
    def test_erstellt_teilaufgabe(self, lehrkraft_client, klausur, aufgabe):
        response = lehrkraft_client.post(
            reverse("editor:teilaufgabe_erstellen", args=[klausur.pk, aufgabe.pk]),
            {"bezeichnung": "1a"},
        )

        assert response.status_code == 200
        assert Teilaufgabe.objects.filter(aufgabe=aufgabe, bezeichnung="1a").exists()

    def test_doppelte_bezeichnung_schlaegt_fehl(self, lehrkraft_client, klausur, aufgabe):
        Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")

        lehrkraft_client.post(
            reverse("editor:teilaufgabe_erstellen", args=[klausur.pk, aufgabe.pk]),
            {"bezeichnung": "1a"},
        )

        assert Teilaufgabe.objects.filter(aufgabe=aufgabe, bezeichnung="1a").count() == 1

    def test_loescht_teilaufgabe(self, lehrkraft_client, klausur, aufgabe):
        teilaufgabe = Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")

        response = lehrkraft_client.post(
            reverse("editor:teilaufgabe_loeschen", args=[klausur.pk, teilaufgabe.pk])
        )

        assert response.status_code == 200
        assert not Teilaufgabe.objects.filter(pk=teilaufgabe.pk).exists()

    def test_fremde_aufgabe_liefert_404(self, lehrkraft_client, fach):
        andere_lehrkraft = Lehrkraft.objects.create_user(
            email="andere@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        andere_klausur = Klausur.objects.create(
            fach=fach,
            jahr=2025,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="x",
            titel="Fremd",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=_pdf_upload(),
            status=Klausur.Status.ENTWURF,
            ersteller=andere_lehrkraft,
        )
        fremde_aufgabe = Aufgabe.objects.create(
            klausur=andere_klausur, nummer=1, pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN
        )

        response = lehrkraft_client.post(
            reverse("editor:teilaufgabe_erstellen", args=[andere_klausur.pk, fremde_aufgabe.pk]),
            {"bezeichnung": "1a"},
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestBereichFuerTeilaufgabe:
    def test_erstellt_bereich_extrahiert_text_und_schlaegt_vor(
        self, lehrkraft_client, klausur, aufgabe, thema_nullstellen
    ):
        teilaufgabe = Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")

        response = lehrkraft_client.post(
            reverse("editor:bereich_erstellen", args=[klausur.pk]),
            {
                "teilaufgabe": teilaufgabe.pk,
                "seite": 1,
                "x0": 0.0,
                "y0": 0.0,
                "x1": 1.0,
                "y1": 1.0,
            },
        )

        assert response.status_code == 200
        daten = response.json()
        assert "Nullstellen" in daten["text"]
        assert daten["seite"] == 1
        assert daten["anforderungsbereich_vorschlag"]["operator"] in ("ermitteln", "begründen")
        assert daten["anforderungsbereich_vorschlag"]["anforderungsbereich"] == "II"
        kennungen = [thema["kennung"] for thema in daten["themen_vorschlaege"]]
        assert "analysis.fkt.nullstellen" in kennungen

        teilaufgabe.refresh_from_db()
        assert teilaufgabe.seite == 1
        assert "Nullstellen" in teilaufgabe.text

    def test_loeschen_letzter_bereich_leert_text_und_seite(
        self, lehrkraft_client, klausur, aufgabe
    ):
        teilaufgabe = Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")
        erstellen_antwort = lehrkraft_client.post(
            reverse("editor:bereich_erstellen", args=[klausur.pk]),
            {
                "teilaufgabe": teilaufgabe.pk,
                "seite": 1,
                "x0": 0.0,
                "y0": 0.0,
                "x1": 1.0,
                "y1": 1.0,
            },
        ).json()

        lehrkraft_client.post(
            reverse("editor:bereich_loeschen", args=[klausur.pk, erstellen_antwort["id"]])
        )

        teilaufgabe.refresh_from_db()
        assert teilaufgabe.text == ""
        assert teilaufgabe.seite is None

    def test_sowohl_aufgabe_als_auch_teilaufgabe_wird_abgelehnt(
        self, lehrkraft_client, klausur, aufgabe
    ):
        teilaufgabe = Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")

        response = lehrkraft_client.post(
            reverse("editor:bereich_erstellen", args=[klausur.pk]),
            {
                "aufgabe": aufgabe.pk,
                "teilaufgabe": teilaufgabe.pk,
                "seite": 1,
                "x0": 0.0,
                "y0": 0.0,
                "x1": 1.0,
                "y1": 1.0,
            },
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestTeilaufgabeAktualisieren:
    def test_speichert_text_punkte_operatoren_und_themen(
        self, lehrkraft_client, klausur, aufgabe, thema_nullstellen
    ):
        teilaufgabe = Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")
        thema = thema_nullstellen

        response = lehrkraft_client.post(
            reverse("editor:teilaufgabe_aktualisieren", args=[klausur.pk, teilaufgabe.pk]),
            {
                "text": "Bestimmen Sie die Nullstellen von f.",
                "punkte": 6,
                "anforderungsbereich": Teilaufgabe.Anforderungsbereich.II,
                "operatoren_text": "bestimmen, begründen",
                "themen": [thema.pk],
            },
        )

        assert response.status_code == 200
        teilaufgabe.refresh_from_db()
        assert teilaufgabe.punkte == 6
        assert teilaufgabe.anforderungsbereich == Teilaufgabe.Anforderungsbereich.II
        assert teilaufgabe.operatoren == ["bestimmen", "begründen"]
        assert list(teilaufgabe.themen.all()) == [thema]

    def test_ohne_anforderungsbereich_bleibt_leer(self, lehrkraft_client, klausur, aufgabe):
        teilaufgabe = Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")

        response = lehrkraft_client.post(
            reverse("editor:teilaufgabe_aktualisieren", args=[klausur.pk, teilaufgabe.pk]),
            {"text": "Ein Text ohne Anforderungsbereich.", "operatoren_text": ""},
        )

        assert response.status_code == 200
        teilaufgabe.refresh_from_db()
        assert teilaufgabe.anforderungsbereich == ""
