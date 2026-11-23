import shutil
from pathlib import Path

import pymupdf
from django.conf import settings


def vorschaubild_verzeichnis(klausur) -> Path:
    return Path(settings.MEDIA_ROOT) / "vorschaubilder" / str(klausur.pk)


def vorschaubilder_erzeugen(klausur, *, zoom: float = 1.5) -> None:
    """Rendert jede Seite der Klausur-PDF als PNG (nur die Klausur-PDF, nicht den
    Erwartungshorizont). Wird nach erfolgreichem Commit aufgerufen, nicht Teil der
    Import-Transaktion, da Dateisystem-Operationen nicht transaktional sind."""
    verzeichnis = vorschaubild_verzeichnis(klausur)
    if verzeichnis.exists():
        shutil.rmtree(verzeichnis)
    verzeichnis.mkdir(parents=True, exist_ok=True)

    matrix = pymupdf.Matrix(zoom, zoom)
    with klausur.pdf.open("rb") as datei:
        dokument = pymupdf.open(stream=datei.read(), filetype="pdf")
        try:
            for seiten_index in range(dokument.page_count):
                seite = dokument.load_page(seiten_index)
                pixmap = seite.get_pixmap(matrix=matrix)
                pixmap.save(verzeichnis / f"seite-{seiten_index + 1}.png")
        finally:
            dokument.close()
