from unittest import mock

import pymupdf

from editor.pdf_text import dokument_mit_textebene_oeffnen, text_aus_bereich, text_fuer_bereiche


def _pdf_mit_text(pfad, text="Hallo Welt"):
    dokument = pymupdf.open()
    seite = dokument.new_page()
    seite.insert_text((72, 72), text, fontsize=24)
    dokument.save(pfad)
    dokument.close()


def _pdf_ohne_text(pfad):
    dokument = pymupdf.open()
    dokument.new_page()
    dokument.save(pfad)
    dokument.close()


class _Bereich:
    def __init__(self, seite, x0, y0, x1, y1):
        self.seite = seite
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class TestTextAusBereich:
    def test_extrahiert_text_im_markierten_bereich(self, tmp_path):
        pdf_pfad = tmp_path / "klausur.pdf"
        _pdf_mit_text(pdf_pfad, "Hallo Welt")

        with pymupdf.open(pdf_pfad) as dokument:
            text = text_aus_bereich(dokument, _Bereich(1, 0, 0, 1, 1))

        assert "Hallo Welt" in text

    def test_leerer_bereich_liefert_leeren_text(self, tmp_path):
        pdf_pfad = tmp_path / "klausur.pdf"
        _pdf_mit_text(pdf_pfad, "Hallo Welt")

        with pymupdf.open(pdf_pfad) as dokument:
            # Bereich ganz unten rechts, weit entfernt vom eingefügten Text.
            text = text_aus_bereich(dokument, _Bereich(1, 0.9, 0.9, 1.0, 1.0))

        assert text == ""


class TestTextFuerBereiche:
    def test_fuegt_mehrere_bereiche_sortiert_zusammen(self, tmp_path):
        pdf_pfad = tmp_path / "klausur.pdf"
        dokument = pymupdf.open()
        seite1 = dokument.new_page()
        seite1.insert_text((72, 72), "Erster Teil", fontsize=24)
        seite2 = dokument.new_page()
        seite2.insert_text((72, 72), "Zweiter Teil", fontsize=24)
        dokument.save(pdf_pfad)
        dokument.close()

        bereiche = [_Bereich(2, 0, 0, 1, 1), _Bereich(1, 0, 0, 1, 1)]
        with pymupdf.open(pdf_pfad) as dokument:
            text = text_fuer_bereiche(dokument, bereiche)

        zeilen = text.splitlines()
        assert "Erster Teil" in zeilen[0]
        assert "Zweiter Teil" in zeilen[-1]


class TestDokumentMitTextebeneOeffnen:
    def test_pdf_mit_textebene_wird_direkt_geoeffnet(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path / "media"
        pdf_pfad = tmp_path / "klausur.pdf"
        _pdf_mit_text(pdf_pfad)

        with mock.patch("ocrmypdf.ocr") as ocr_mock:
            dokument = dokument_mit_textebene_oeffnen(pdf_pfad)
            dokument.close()

        ocr_mock.assert_not_called()

    def test_pdf_ohne_textebene_ruft_ocr_auf(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path / "media"
        pdf_pfad = tmp_path / "scan.pdf"
        _pdf_ohne_text(pdf_pfad)

        def fake_ocr(eingabe, ausgabe, **kwargs):
            _pdf_mit_text(ausgabe, "OCR-Text")

        with mock.patch("ocrmypdf.ocr", side_effect=fake_ocr) as ocr_mock:
            dokument = dokument_mit_textebene_oeffnen(pdf_pfad)
            try:
                assert "OCR-Text" in dokument[0].get_text()
            finally:
                dokument.close()

        ocr_mock.assert_called_once()

    def test_ocr_ergebnis_wird_zwischengespeichert(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path / "media"
        pdf_pfad = tmp_path / "scan.pdf"
        _pdf_ohne_text(pdf_pfad)

        def fake_ocr(eingabe, ausgabe, **kwargs):
            _pdf_mit_text(ausgabe, "OCR-Text")

        with mock.patch("ocrmypdf.ocr", side_effect=fake_ocr) as ocr_mock:
            dokument_mit_textebene_oeffnen(pdf_pfad).close()
            dokument_mit_textebene_oeffnen(pdf_pfad).close()

        ocr_mock.assert_called_once()

    def test_fehlschlagende_ocr_faellt_auf_original_zurueck(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path / "media"
        pdf_pfad = tmp_path / "scan.pdf"
        _pdf_ohne_text(pdf_pfad)

        with mock.patch("ocrmypdf.ocr", side_effect=RuntimeError("tesseract fehlt")):
            dokument = dokument_mit_textebene_oeffnen(pdf_pfad)
            try:
                assert dokument.page_count == 1
            finally:
                dokument.close()
