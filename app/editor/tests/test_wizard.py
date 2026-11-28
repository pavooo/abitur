import pymupdf
import pytest
from accounts.models import Lehrkraft
from archiv.models import Fach, Klausur
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


def _echtes_pdf(seiten=1) -> bytes:
    dokument = pymupdf.open()
    for _ in range(seiten):
        dokument.new_page()
    daten = dokument.tobytes()
    dokument.close()
    return daten


def _pdf_upload(name="klausur.pdf", seiten=1):
    return SimpleUploadedFile(name, _echtes_pdf(seiten), content_type="application/pdf")


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


def _metadaten(fach, **overrides):
    daten = {
        "fach": fach.pk,
        "jahr": 2025,
        "kursart": Klausur.Kursart.LK,
        "termin": Klausur.Termin.HAUPTTERMIN,
        "variante": "A",
        "hilfsmittel": Klausur.Hilfsmittel.TR,
        "titel": "Analysis",
    }
    daten.update(overrides)
    return daten


@pytest.mark.django_db
class TestSchritt1Metadaten:
    def test_anlegen_erstellt_entwurf(self, lehrkraft_client, fach):
        response = lehrkraft_client.post(reverse("editor:schritt1_neu"), _metadaten(fach))

        klausur = Klausur.objects.get(titel="Analysis")
        assert klausur.status == Klausur.Status.ENTWURF
        assert klausur.ersteller == lehrkraft_client.lehrkraft
        assert response.status_code == 302
        assert response.url == reverse("editor:schritt2", args=[klausur.pk])

    def test_ohne_termin_schlaegt_fehl(self, lehrkraft_client, fach):
        daten = _metadaten(fach)
        del daten["termin"]

        response = lehrkraft_client.post(reverse("editor:schritt1_neu"), daten)

        assert response.status_code == 200
        assert not Klausur.objects.filter(titel="Analysis").exists()

    def test_warnt_bei_bestehendem_schluessel(self, lehrkraft_client, fach):
        Klausur.objects.create(
            fach=fach,
            jahr=2025,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            variante="A",
            titel="Bestehend",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=_pdf_upload(),
            status=Klausur.Status.FREIGEGEBEN,
        )

        response = lehrkraft_client.post(
            reverse("editor:schritt1_neu"), _metadaten(fach, titel="Neu")
        )

        assert response.status_code == 200
        assert "existiert bereits" in response.content.decode()

    def test_fach_beschraenkt_auf_zugeordnete_faecher(self, lehrkraft_client, fach):
        Fach.objects.get_or_create(kuerzel="D", defaults={"name": "Deutsch"})

        response = lehrkraft_client.get(reverse("editor:schritt1_neu"))

        faecher = list(response.context["form"].fields["fach"].queryset)
        assert faecher == [fach]

    def test_forcierte_fachfremde_fach_id_wird_abgelehnt(self, lehrkraft_client, fach):
        anderes_fach, _ = Fach.objects.get_or_create(kuerzel="D", defaults={"name": "Deutsch"})
        daten = _metadaten(fach)
        daten["fach"] = anderes_fach.pk

        response = lehrkraft_client.post(reverse("editor:schritt1_neu"), daten)

        assert response.status_code == 200
        assert not Klausur.objects.filter(fach=anderes_fach).exists()

    def test_bearbeiten_aendert_bestehenden_entwurf(self, lehrkraft_client, fach):
        klausur = Klausur.objects.create(
            fach=fach,
            jahr=2025,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            titel="Alt",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            status=Klausur.Status.ENTWURF,
            ersteller=lehrkraft_client.lehrkraft,
        )

        response = lehrkraft_client.post(
            reverse("editor:schritt1", args=[klausur.pk]), _metadaten(fach, titel="Neu")
        )

        klausur.refresh_from_db()
        assert klausur.titel == "Neu"
        assert response.status_code == 302


@pytest.mark.django_db
class TestSchritt2Pdf:
    def _entwurf(self, fach, lehrkraft, **overrides):
        daten = {
            "fach": fach,
            "jahr": 2025,
            "kursart": Klausur.Kursart.LK,
            "termin": Klausur.Termin.HAUPTTERMIN,
            "titel": "Analysis",
            "hilfsmittel": Klausur.Hilfsmittel.TR,
            "status": Klausur.Status.ENTWURF,
            "ersteller": lehrkraft,
        }
        daten.update(overrides)
        return Klausur.objects.create(**daten)

    def test_pdf_ist_pflicht_wenn_noch_keines_hochgeladen(self, lehrkraft_client, fach):
        klausur = self._entwurf(fach, lehrkraft_client.lehrkraft)

        response = lehrkraft_client.post(reverse("editor:schritt2", args=[klausur.pk]), {})

        assert response.status_code == 200
        assert "Pflicht" in response.content.decode()

    def test_gueltige_pdf_wird_gespeichert_und_bleibt_auf_schritt2(self, lehrkraft_client, fach):
        klausur = self._entwurf(fach, lehrkraft_client.lehrkraft)

        response = lehrkraft_client.post(
            reverse("editor:schritt2", args=[klausur.pk]), {"pdf": _pdf_upload()}
        )

        klausur.refresh_from_db()
        assert klausur.pdf
        assert response.status_code == 302
        assert response.url == reverse("editor:schritt2", args=[klausur.pk])

    def test_ungueltige_pdf_wird_abgelehnt(self, lehrkraft_client, fach):
        klausur = self._entwurf(fach, lehrkraft_client.lehrkraft)
        kaputte_datei = SimpleUploadedFile(
            "klausur.pdf", b"Kein PDF", content_type="application/pdf"
        )

        response = lehrkraft_client.post(
            reverse("editor:schritt2", args=[klausur.pk]), {"pdf": kaputte_datei}
        )

        klausur.refresh_from_db()
        assert not klausur.pdf
        assert response.status_code == 200

    def test_erneuter_aufruf_ohne_neue_datei_behaelt_vorhandenes_pdf(self, lehrkraft_client, fach):
        klausur = self._entwurf(fach, lehrkraft_client.lehrkraft, pdf=_pdf_upload())

        response = lehrkraft_client.post(reverse("editor:schritt2", args=[klausur.pk]), {})

        assert response.status_code == 302
        assert response.url == reverse("editor:schritt2", args=[klausur.pk])


@pytest.mark.django_db
class TestZugriffsschutz:
    def test_fremde_klausur_liefert_404(self, lehrkraft_client, fach):
        andere_lehrkraft = Lehrkraft.objects.create_user(
            email="andere@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        klausur = Klausur.objects.create(
            fach=fach,
            jahr=2025,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            titel="Analysis",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            status=Klausur.Status.ENTWURF,
            ersteller=andere_lehrkraft,
        )

        response = lehrkraft_client.get(reverse("editor:schritt1", args=[klausur.pk]))

        assert response.status_code == 404

    def test_freigegebene_klausur_kann_ersteller_nicht_mehr_bearbeiten(
        self, lehrkraft_client, fach
    ):
        klausur = Klausur.objects.create(
            fach=fach,
            jahr=2025,
            kursart=Klausur.Kursart.LK,
            termin=Klausur.Termin.HAUPTTERMIN,
            titel="Analysis",
            hilfsmittel=Klausur.Hilfsmittel.TR,
            pdf=_pdf_upload(),
            status=Klausur.Status.FREIGEGEBEN,
            ersteller=lehrkraft_client.lehrkraft,
        )

        response = lehrkraft_client.get(reverse("editor:schritt1", args=[klausur.pk]))

        assert response.status_code == 404

    def test_anonym_wird_zum_login_umgeleitet(self, client, fach):
        response = client.get(reverse("editor:schritt1_neu"))
        assert response.status_code == 302
        assert reverse("accounts:login_waehlen") in response.url
