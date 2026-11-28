"""Sicherheitsprüfung für PDF-Uploads im Lehrkraft-Editor (CLAUDE.md, Abschnitt
Lehrkraft-Editor → Sicherheit). Reine Funktion, unabhängig von Django-Forms, damit sie
ohne Request/Formular-Plumbing testbar ist.
"""

import pymupdf
from django.conf import settings

ERLAUBTE_ENDUNG = ".pdf"
ERLAUBTE_MIME_TYPEN = {"application/pdf", "application/x-pdf"}
PDF_MAGIC_BYTES = b"%PDF-"


class PdfPruefungFehler(Exception):
    """Die Datei hat eine der Prüfungen nicht bestanden; die Meldung ist auf Deutsch
    und für die Anzeige im Formular gedacht."""


def pruefe_pdf(datei) -> int:
    """Prüft Dateiendung, MIME-Typ, Magic Bytes, Öffnen mit PyMuPDF sowie Größen- und
    Seitenlimit. Gibt bei Erfolg die Seitenzahl zurück, sonst `PdfPruefungFehler`."""
    name = datei.name or ""
    if not name.lower().endswith(ERLAUBTE_ENDUNG):
        raise PdfPruefungFehler("Die Datei muss die Endung „.pdf“ haben.")

    if datei.content_type not in ERLAUBTE_MIME_TYPEN:
        raise PdfPruefungFehler("Die Datei muss vom Typ PDF sein.")

    max_bytes = settings.KLAUSUR_PDF_MAX_MB * 1024 * 1024
    if datei.size > max_bytes:
        raise PdfPruefungFehler(
            f"Die Datei darf höchstens {settings.KLAUSUR_PDF_MAX_MB} MB groß sein."
        )

    datei.seek(0)
    inhalt = datei.read()
    datei.seek(0)

    if not inhalt.startswith(PDF_MAGIC_BYTES):
        raise PdfPruefungFehler("Die Datei ist keine gültige PDF-Datei.")

    try:
        dokument = pymupdf.open(stream=inhalt, filetype="pdf")
    except Exception as exc:
        raise PdfPruefungFehler("Die PDF-Datei konnte nicht geöffnet werden.") from exc

    try:
        seitenzahl = dokument.page_count
    finally:
        dokument.close()

    if seitenzahl > settings.KLAUSUR_PDF_MAX_SEITEN:
        raise PdfPruefungFehler(
            f"Die PDF-Datei darf höchstens {settings.KLAUSUR_PDF_MAX_SEITEN} Seiten haben."
        )

    return seitenzahl
