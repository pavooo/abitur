"""Geschützte Auslieferung von Klausur-Dateien (PDF, Erwartungshorizont,
Seitenvorschaubilder). Dateien liegen außerhalb des Webroots; Auslieferung
ausschließlich über Views mit Rechteprüfung (siehe CLAUDE.md, Abschnitt
Nachschreibklausuren) – niemals direkt über den Webserver.
"""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse

from .models import NachschreibZugriff
from .sichtbarkeit import Termin


def vorschaubild_pfad(klausur, seite: int) -> Path:
    """Muss mit `importer.vorschaubilder.vorschaubild_verzeichnis` übereinstimmen.
    Keine direkte Abhängigkeit zu `importer`, da `archiv` dessen Import-Pipeline
    nicht kennen soll (siehe CLAUDE.md, Projektstruktur)."""
    return Path(settings.MEDIA_ROOT) / "vorschaubilder" / str(klausur.pk) / f"seite-{seite}.png"


def protokolliere_falls_nachschreibklausur(request, klausur) -> None:
    """Jeder Abruf einer Nachschreibklausur wird protokolliert (Lehrkraft, Zeitpunkt,
    Klausur). SuS können diesen Punkt nie erreichen, da `sichtbar_fuer` ihnen
    Nachschreibklausuren bereits auf Datenbankebene vorenthält (404 statt 403)."""
    if klausur.termin != Termin.NACHSCHREIBTERMIN:
        return
    lehrkraft = getattr(request, "user", None)
    if lehrkraft is not None and lehrkraft.is_authenticated:
        NachschreibZugriff.objects.create(lehrkraft=lehrkraft, klausur=klausur)


def datei_ausliefern(pfad: Path, dateiname: str, *, content_type: str) -> HttpResponse:
    """Liefert eine Datei aus: im Dev-Modus (DEBUG) direkt per FileResponse, da kein
    nginx davorsteht; in Produktion per X-Accel-Redirect, sodass nginx die Datei
    tatsächlich ausliefert und Django nur die Rechteprüfung übernimmt."""
    if not pfad.exists():
        raise Http404("Datei nicht gefunden.")

    if settings.DEBUG:
        return FileResponse(open(pfad, "rb"), content_type=content_type, filename=dateiname)

    response = HttpResponse(content_type=content_type)
    interner_pfad = pfad.relative_to(settings.MEDIA_ROOT)
    response["X-Accel-Redirect"] = f"{settings.GESCHUETZTE_MEDIEN_INTERNER_PFAD}{interner_pfad}"
    response["Content-Disposition"] = f'inline; filename="{dateiname}"'
    return response
