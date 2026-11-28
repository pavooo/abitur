import json

import pymupdf
import pytest
from accounts.models import Lehrkraft
from archiv.models import Aufgabe, Fach, Klausur, Teilaufgabe, Thema
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from editor import option_c


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
def thema(fach):
    return Thema.objects.create(fach=fach, kennung="analysis.diff.wendepunkt", name="Wendepunkte")


@pytest.fixture
def thema_wachstum(fach):
    return Thema.objects.create(fach=fach, kennung="analysis.anwendung.wachstum", name="Wachstum")


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
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        variante="A",
        titel="Analysis – Prüfungsteil B",
        hilfsmittel=Klausur.Hilfsmittel.TR,
        pdf=_pdf_upload(),
        status=Klausur.Status.ENTWURF,
        ersteller=lehrkraft_client.lehrkraft,
    )


def _gueltiges_json(**overrides):
    daten = json.loads(json.dumps(option_c.BEISPIEL_JSON))
    daten.update(overrides)
    return daten


@pytest.mark.django_db
class TestErzeugePrompt:
    def test_enthaelt_metadaten_und_themen(self, klausur, thema):
        prompt = option_c.erzeuge_prompt(klausur)

        assert klausur.titel in prompt
        assert "haupttermin" in prompt
        assert thema.kennung in prompt
        assert "AUSSCHLIESSLICH gültiges JSON" in prompt


@pytest.mark.django_db
class TestValidiere:
    def test_kein_json_liefert_fehler(self, klausur):
        ergebnis = option_c.validiere("kein json", klausur=klausur)
        assert not ergebnis.gueltig
        assert ergebnis.fehler

    def test_ohne_aufgaben_schlaegt_fehl(self, klausur):
        ergebnis = option_c.validiere(json.dumps({}), klausur=klausur)
        assert not ergebnis.gueltig

    def test_unbekanntes_thema_wird_gemeldet(self, klausur, thema):
        daten = _gueltiges_json()
        daten["aufgaben"][0]["teilaufgaben"][0]["themen"] = ["analysis.nicht.vorhanden"]

        ergebnis = option_c.validiere(json.dumps(daten), klausur=klausur)

        assert not ergebnis.gueltig
        assert any("existiert nicht" in fehler for fehler in ergebnis.fehler)

    def test_gueltiges_json_ohne_abweichung_hat_keine_konflikte(
        self, klausur, thema, thema_wachstum
    ):
        daten = _gueltiges_json(
            fach=klausur.fach.kuerzel,
            jahr=klausur.jahr,
            kursart=klausur.kursart,
            termin=klausur.termin,
            variante=klausur.variante,
            titel=klausur.titel,
            hilfsmittel=klausur.hilfsmittel,
        )

        ergebnis = option_c.validiere(json.dumps(daten), klausur=klausur)

        assert ergebnis.gueltig
        assert ergebnis.konflikte == []

    def test_abweichender_termin_wird_als_konflikt_gemeldet(self, klausur, thema, thema_wachstum):
        daten = _gueltiges_json(termin=Klausur.Termin.NACHSCHREIBTERMIN)

        ergebnis = option_c.validiere(json.dumps(daten), klausur=klausur)

        assert ergebnis.gueltig
        konflikt_felder = [k["feld"] for k in ergebnis.konflikte]
        assert "termin" in konflikt_felder

    def test_doppelte_aufgabennummern_schlagen_fehl(self, klausur, thema):
        daten = _gueltiges_json()
        zweite_aufgabe = json.loads(json.dumps(daten["aufgaben"][0]))
        daten["aufgaben"].append(zweite_aufgabe)

        ergebnis = option_c.validiere(json.dumps(daten), klausur=klausur)

        assert not ergebnis.gueltig


@pytest.mark.django_db
class TestUebernehmen:
    def test_erstellt_aufgabe_und_teilaufgabe(self, klausur, thema):
        daten = _gueltiges_json()

        option_c.uebernehmen(klausur, daten)

        aufgabe = Aufgabe.objects.get(klausur=klausur, nummer=1)
        assert aufgabe.seite_von == 2
        assert aufgabe.seite_bis == 3
        teilaufgabe = Teilaufgabe.objects.get(aufgabe=aufgabe, bezeichnung="1c")
        assert teilaufgabe.seite == 3
        assert teilaufgabe.punkte == 6
        assert list(teilaufgabe.themen.values_list("kennung", flat=True)) == [thema.kennung]
        # Option C liefert nur Seitenzahlen, keine Koordinaten – es entsteht bewusst
        # kein Bereich (der wird später in Schritt 3 nachgezeichnet).
        assert teilaufgabe.bereiche.count() == 0

    def test_bestehende_bereiche_bleiben_bei_erneutem_uebernehmen_erhalten(self, klausur, thema):
        from archiv.models import Bereich

        daten = _gueltiges_json()
        option_c.uebernehmen(klausur, daten)
        teilaufgabe = Teilaufgabe.objects.get(aufgabe__klausur=klausur, bezeichnung="1c")
        bereich = Bereich.objects.create(teilaufgabe=teilaufgabe, seite=3, x0=0, y0=0, x1=1, y1=1)

        geaenderte_daten = _gueltiges_json()
        geaenderte_daten["aufgaben"][0]["teilaufgaben"][0]["text"] = "Neuer Text"
        option_c.uebernehmen(klausur, geaenderte_daten)

        teilaufgabe.refresh_from_db()
        assert teilaufgabe.text == "Neuer Text"
        assert Bereich.objects.filter(pk=bereich.pk).exists()


@pytest.mark.django_db
class TestOptionCView:
    def test_get_zeigt_prompt(self, lehrkraft_client, klausur, thema):
        response = lehrkraft_client.get(reverse("editor:option_c", args=[klausur.pk]))
        assert response.status_code == 200
        assert klausur.titel in response.content.decode()

    def test_post_mit_fehlerhaftem_json_zeigt_fehler(self, lehrkraft_client, klausur):
        response = lehrkraft_client.post(
            reverse("editor:option_c", args=[klausur.pk]), {"json_text": "kaputt"}
        )
        assert response.status_code == 200
        assert "Fehler" in response.content.decode()
        assert not Aufgabe.objects.filter(klausur=klausur).exists()

    def test_post_mit_konflikt_ohne_bestaetigung_uebernimmt_nicht(
        self, lehrkraft_client, klausur, thema, thema_wachstum
    ):
        daten = _gueltiges_json(termin=Klausur.Termin.NACHSCHREIBTERMIN)

        response = lehrkraft_client.post(
            reverse("editor:option_c", args=[klausur.pk]), {"json_text": json.dumps(daten)}
        )

        assert response.status_code == 200
        assert "Abweichungen" in response.content.decode()
        assert not Aufgabe.objects.filter(klausur=klausur).exists()

    def test_post_mit_bestaetigtem_konflikt_uebernimmt(
        self, lehrkraft_client, klausur, thema, thema_wachstum
    ):
        daten = _gueltiges_json(termin=Klausur.Termin.NACHSCHREIBTERMIN)

        response = lehrkraft_client.post(
            reverse("editor:option_c", args=[klausur.pk]),
            {"json_text": json.dumps(daten), "konflikte_bestaetigt": "1"},
        )

        assert response.status_code == 302
        assert Aufgabe.objects.filter(klausur=klausur, nummer=1).exists()
        # Schritt 1 (Haupttermin) behält auch bei bestätigtem Konflikt Vorrang.
        klausur.refresh_from_db()
        assert klausur.termin == Klausur.Termin.HAUPTTERMIN

    def test_fremde_klausur_liefert_404(self, lehrkraft_client, fach):
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

        response = lehrkraft_client.get(reverse("editor:option_c", args=[andere_klausur.pk]))

        assert response.status_code == 404


@pytest.mark.django_db
class TestOptionCFormat:
    def test_erreichbar_fuer_angemeldete_lehrkraft(self, lehrkraft_client):
        response = lehrkraft_client.get(reverse("editor:option_c_format"))
        assert response.status_code == 200

    def test_erfordert_login(self, client):
        response = client.get(reverse("editor:option_c_format"))
        assert response.status_code == 302
