import pymupdf
import pytest
from archiv.models import Aufgabe, Fach, Klausur, Teilaufgabe, Thema
from django.core.files.uploadedfile import SimpleUploadedFile

from editor.vollstaendigkeit import pruefe


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
def klausur(fach, db):
    return Klausur.objects.create(
        fach=fach,
        jahr=2025,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        titel="Analysis",
        hilfsmittel=Klausur.Hilfsmittel.TR,
        status=Klausur.Status.ENTWURF,
    )


@pytest.mark.django_db
class TestPruefe:
    def test_ohne_pdf_ist_luecke(self, klausur):
        ergebnis = pruefe(klausur)
        assert any("PDF" in luecke for luecke in ergebnis.pflicht_luecken)
        assert not ergebnis.ist_vollstaendig

    def test_ohne_aufgaben_ist_luecke(self, klausur):
        klausur.pdf = _pdf_upload()
        klausur.save()

        ergebnis = pruefe(klausur)

        assert any("Aufgaben angelegt" in luecke for luecke in ergebnis.pflicht_luecken)

    def test_aufgabe_ohne_bereich_ist_luecke(self, klausur):
        klausur.pdf = _pdf_upload()
        klausur.save()
        Aufgabe.objects.create(
            klausur=klausur, nummer=1, pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN
        )

        ergebnis = pruefe(klausur)

        assert any("Aufgabe 1: kein Bereich" in luecke for luecke in ergebnis.pflicht_luecken)
        assert any("keine Teilaufgaben" in luecke for luecke in ergebnis.pflicht_luecken)

    def test_teilaufgabe_ohne_text_seite_oder_afb_ist_luecke(self, klausur):
        klausur.pdf = _pdf_upload()
        klausur.save()
        aufgabe = Aufgabe.objects.create(
            klausur=klausur,
            nummer=1,
            seite_von=1,
            seite_bis=1,
            pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN,
        )
        Teilaufgabe.objects.create(aufgabe=aufgabe, bezeichnung="1a")

        ergebnis = pruefe(klausur)

        luecken_text = " ".join(ergebnis.pflicht_luecken)
        assert "Teilaufgabe 1a: kein Bereich markiert" in luecken_text
        assert "Teilaufgabe 1a: kein Text" in luecken_text
        assert "Teilaufgabe 1a: kein Anforderungsbereich" in luecken_text

    def test_teilaufgabe_ohne_thema_ist_nur_hinweis(self, klausur):
        from archiv.models import Bereich

        klausur.pdf = _pdf_upload()
        klausur.save()
        aufgabe = Aufgabe.objects.create(
            klausur=klausur,
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

        ergebnis = pruefe(klausur)

        assert ergebnis.ist_vollstaendig
        assert any("kein Thema zugeordnet" in hinweis for hinweis in ergebnis.hinweise)

    def test_vollstaendige_klausur_hat_keine_pflicht_luecken(self, klausur, fach):
        from archiv.models import Bereich

        klausur.pdf = _pdf_upload()
        klausur.save()
        aufgabe = Aufgabe.objects.create(
            klausur=klausur,
            nummer=1,
            seite_von=1,
            seite_bis=1,
            pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN,
        )
        Bereich.objects.create(aufgabe=aufgabe, seite=1, x0=0, y0=0, x1=1, y1=1)
        thema = Thema.objects.create(fach=fach, kennung="analysis.x", name="X")
        teilaufgabe = Teilaufgabe.objects.create(
            aufgabe=aufgabe,
            bezeichnung="1a",
            seite=1,
            text="Text",
            anforderungsbereich=Teilaufgabe.Anforderungsbereich.I,
        )
        Bereich.objects.create(teilaufgabe=teilaufgabe, seite=1, x0=0, y0=0, x1=1, y1=1)
        teilaufgabe.themen.add(thema)

        ergebnis = pruefe(klausur)

        assert ergebnis.ist_vollstaendig
        assert ergebnis.hinweise == []

    def test_seite_ohne_echten_bereich_ist_trotzdem_luecke(self, klausur, fach):
        """Option C setzt `seite_von`/`seite_bis`/`seite` direkt aus dem JSON, ohne
        einen Bereich anzulegen (CLAUDE.md, Abschnitt Option C) – das muss weiterhin
        als Lücke erscheinen, bis die Lehrkraft den Bereich nachzeichnet."""
        klausur.pdf = _pdf_upload()
        klausur.save()
        aufgabe = Aufgabe.objects.create(
            klausur=klausur,
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

        ergebnis = pruefe(klausur)

        luecken_text = " ".join(ergebnis.pflicht_luecken)
        assert "Aufgabe 1: kein Bereich markiert" in luecken_text
        assert "Teilaufgabe 1a: kein Bereich markiert" in luecken_text
