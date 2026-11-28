"""Textextraktion aus markierten Bereichen für den Lehrkraft-Editor (CLAUDE.md,
Abschnitt Lehrkraft-Editor → Bereichsmarkierung): befüllt den Text einer Teilaufgabe
vor, indem der Inhalt ihrer Bereiche aus dem Klausur-PDF ausgelesen wird. Seiten ohne
Textebene (reine Scans) werden vorher mit OCRmyPDF durchsucht; schlägt das fehl (z. B.
fehlende Tesseract-Installation), wird stillschweigend auf leeren Text zurückgefallen –
der Text ist ohnehin nur eine Vorbefüllung und bleibt bearbeitbar.
"""

import hashlib
import logging
from pathlib import Path

import pymupdf
from django.conf import settings

logger = logging.getLogger(__name__)


def text_aus_bereich(dokument: pymupdf.Document, bereich) -> str:
    """Extrahiert den Text eines einzelnen Bereichs (normierte 0–1-Koordinaten) von
    seiner Seite mit `get_text(clip=...)`."""
    seite = dokument.load_page(bereich.seite - 1)
    breite, hoehe = seite.rect.width, seite.rect.height
    clip = pymupdf.Rect(
        bereich.x0 * breite, bereich.y0 * hoehe, bereich.x1 * breite, bereich.y1 * hoehe
    )
    return seite.get_text("text", clip=clip).strip()


def text_fuer_bereiche(dokument: pymupdf.Document, bereiche) -> str:
    """Fügt die Texte mehrerer Bereiche (ggf. über mehrere Seiten) zu einem Vorschlag
    zusammen, sortiert nach Seite und vertikaler Position."""
    sortierte = sorted(bereiche, key=lambda bereich: (bereich.seite, bereich.y0))
    texte = [text_aus_bereich(dokument, bereich) for bereich in sortierte]
    return "\n".join(text for text in texte if text)


def _hat_textebene(dokument: pymupdf.Document) -> bool:
    return any(seite.get_text().strip() for seite in dokument)


def _ocr_cache_pfad(pdf_pfad: Path) -> Path:
    """Dateiname aus dem Inhalts-Hash statt der Klausur-ID: ein erneuter Upload
    derselben Klausur bekommt dadurch automatisch einen neuen Cache-Eintrag, ohne dass
    der Upload-Code den alten explizit invalidieren muss."""
    pruefsumme = hashlib.sha256(pdf_pfad.read_bytes()).hexdigest()
    return Path(settings.MEDIA_ROOT) / "ocr-cache" / f"{pruefsumme}.pdf"


def dokument_mit_textebene_oeffnen(pdf_pfad: Path) -> pymupdf.Document:
    """Öffnet die PDF und sorgt dafür, dass jede Seite (so gut es geht) eine Textebene
    hat: Dokumente mit Textebene werden direkt zurückgegeben, reine Scans vorher per
    OCRmyPDF verarbeitet (Ergebnis zwischengespeichert, da OCR vergleichsweise langsam
    ist). Schlägt OCR fehl oder ist nicht verfügbar, wird die Original-PDF
    zurückgegeben – Textextraktion liefert dann leere Strings, Punkt 4 der
    CLAUDE.md-Sicherheitsbetrachtung („bearbeitbar“) fängt das ab."""
    dokument = pymupdf.open(pdf_pfad)
    if _hat_textebene(dokument):
        return dokument
    dokument.close()

    cache_pfad = _ocr_cache_pfad(pdf_pfad)
    if cache_pfad.exists():
        return pymupdf.open(cache_pfad)

    try:
        import ocrmypdf

        cache_pfad.parent.mkdir(parents=True, exist_ok=True)
        ocrmypdf.ocr(
            pdf_pfad,
            cache_pfad,
            language="deu",
            skip_text=True,
            output_type="pdf",
            progress_bar=False,
        )
        return pymupdf.open(cache_pfad)
    except Exception:
        logger.warning("OCR für %s fehlgeschlagen, Text bleibt leer vorbefüllt.", pdf_pfad)
        return pymupdf.open(pdf_pfad)
