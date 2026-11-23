"""Zentrale Sichtbarkeitslogik für Klausuren (siehe CLAUDE.md, Abschnitt
Nachschreibklausuren – SICHERHEITSKRITISCH).

Dieses Modul kennt absichtlich keine Modelle aus `archiv.models`, damit
`Klausur` (und alle anderen Modelle) es gefahrlos importieren können.
"""

import dataclasses

from django.db import models

# Session-Schlüssel für den Lehrkraft-Schalter "Nachschreibklausuren anzeigen"
# (Umschalter/Banner folgen erst mit der Klausuransicht in Phase 5).
NACHSCHREIBMODUS_SESSION_KEY = "nachschreibmodus_aktiv"


class Termin(models.TextChoices):
    HAUPTTERMIN = "haupttermin", "Haupttermin"
    NACHSCHREIBTERMIN = "nachschreibtermin", "Nachschreibtermin"


@dataclasses.dataclass(frozen=True)
class Sichtbarkeitskontext:
    fach_ids: list
    erlaubte_termine: list


def sichtbarkeitskontext_fuer(request) -> Sichtbarkeitskontext:
    """Leitet aus dem Request ab, welche Fächer/Termine sichtbar sein dürfen.

    SuS: nur das Fach ihres Zugangscodes, ausschließlich Haupttermin.
    Lehrkraft: nur zugeordnete Fächer; Nachschreibtermin nur bei aktivem
    Nachschreibmodus (Session-Flag). Admin-Lehrkräfte sind hier bewusst
    nicht privilegiert – sie sehen wie jede Lehrkraft nur ihre Fächer.
    Alles andere (anonym, keine gültige Session): nichts (Standard: verweigern).
    """
    sus_zugangscode = getattr(request, "sus_zugangscode", None)
    if sus_zugangscode is not None:
        return Sichtbarkeitskontext(
            fach_ids=[sus_zugangscode.fach_id], erlaubte_termine=[Termin.HAUPTTERMIN]
        )

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        fach_ids = list(user.faecher.values_list("id", flat=True))
        if request.session.get(NACHSCHREIBMODUS_SESSION_KEY, False):
            erlaubte_termine = [Termin.HAUPTTERMIN, Termin.NACHSCHREIBTERMIN]
        else:
            erlaubte_termine = [Termin.HAUPTTERMIN]
        return Sichtbarkeitskontext(fach_ids=fach_ids, erlaubte_termine=erlaubte_termine)

    return Sichtbarkeitskontext(fach_ids=[], erlaubte_termine=[])
