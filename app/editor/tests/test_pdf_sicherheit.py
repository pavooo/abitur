import pymupdf
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from editor.pdf_sicherheit import PdfPruefungFehler, pruefe_pdf


def _echtes_pdf(seiten=1) -> bytes:
    dokument = pymupdf.open()
    for _ in range(seiten):
        dokument.new_page()
    daten = dokument.tobytes()
    dokument.close()
    return daten


def _upload(name="klausur.pdf", inhalt=None, content_type="application/pdf"):
    if inhalt is None:
        inhalt = _echtes_pdf()
    return SimpleUploadedFile(name, inhalt, content_type=content_type)


class TestPruefePdf:
    def test_gueltige_pdf_wird_akzeptiert(self):
        assert pruefe_pdf(_upload()) == 1

    def test_mehrseitige_pdf_liefert_seitenzahl(self):
        assert pruefe_pdf(_upload(inhalt=_echtes_pdf(seiten=3))) == 3

    def test_falsche_endung_wird_abgelehnt(self):
        with pytest.raises(PdfPruefungFehler):
            pruefe_pdf(_upload(name="klausur.txt"))

    def test_falscher_mime_typ_wird_abgelehnt(self):
        with pytest.raises(PdfPruefungFehler):
            pruefe_pdf(_upload(content_type="text/plain"))

    def test_falsche_magic_bytes_werden_abgelehnt(self):
        with pytest.raises(PdfPruefungFehler):
            pruefe_pdf(_upload(inhalt=b"Kein PDF"))

    def test_defekte_pdf_wird_abgelehnt(self):
        with pytest.raises(PdfPruefungFehler):
            pruefe_pdf(_upload(inhalt=b"%PDF-1.4 kaputt"))

    @override_settings(KLAUSUR_PDF_MAX_MB=1)
    def test_zu_grosse_datei_wird_abgelehnt(self):
        # Angehängte Nullbytes nach dem gültigen PDF-Inhalt ändern nichts an dessen
        # Gültigkeit, machen die Datei aber größer als das (hier verkleinerte) Limit.
        grosse_datei = _upload(inhalt=_echtes_pdf() + b"\x00" * (2 * 1024 * 1024))
        with pytest.raises(PdfPruefungFehler):
            pruefe_pdf(grosse_datei)

    @override_settings(KLAUSUR_PDF_MAX_SEITEN=1)
    def test_zu_viele_seiten_werden_abgelehnt(self):
        with pytest.raises(PdfPruefungFehler):
            pruefe_pdf(_upload(inhalt=_echtes_pdf(seiten=2)))
