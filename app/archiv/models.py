from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.db import models

from .sichtbarkeit import Status, Termin, sichtbarkeitskontext_fuer


class Fach(models.Model):
    name = models.CharField(max_length=100, unique=True)
    kuerzel = models.CharField(max_length=10, unique=True)

    class Meta:
        verbose_name = "Fach"
        verbose_name_plural = "Fächer"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Thema(models.Model):
    fach = models.ForeignKey(
        Fach, verbose_name="Fach", on_delete=models.CASCADE, related_name="themen"
    )
    eltern = models.ForeignKey(
        "self",
        verbose_name="Eltern-Thema",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="kinder",
    )

    class Kursniveau(models.TextChoices):
        ALLE = "alle", "Alle Kursarten"
        LK = "LK", "Nur Leistungskurs"

    kennung = models.CharField("Kennung", max_length=200)
    name = models.CharField("Name", max_length=200)
    synonyme = ArrayField(
        models.CharField(max_length=100), verbose_name="Synonyme", default=list, blank=True
    )
    kursniveau = models.CharField(
        "Kursniveau", max_length=10, choices=Kursniveau.choices, default=Kursniveau.ALLE
    )

    class Meta:
        verbose_name = "Thema"
        verbose_name_plural = "Themen"
        constraints = [
            models.UniqueConstraint(fields=["fach", "kennung"], name="eindeutige_kennung_je_fach"),
        ]
        ordering = ["fach", "kennung"]

    def __str__(self):
        return f"{self.name} ({self.kennung})"

    def clean(self):
        super().clean()
        if self.eltern_id and self.eltern.fach_id != self.fach_id:
            raise ValidationError("Das Eltern-Thema muss zum selben Fach gehören.")


class KlausurQuerySet(models.QuerySet):
    def sichtbar_fuer(self, request):
        kontext = sichtbarkeitskontext_fuer(request)
        return self.filter(
            kontext.status_filter,
            fach_id__in=kontext.fach_ids,
            termin__in=kontext.erlaubte_termine,
        )


class Klausur(models.Model):
    Termin = Termin
    Status = Status

    class Kursart(models.TextChoices):
        GK = "GK", "Grundkurs"
        LK = "LK", "Leistungskurs"

    class Hilfsmittel(models.TextChoices):
        TR = "TR", "Taschenrechner (WTR/GTR)"
        CAS = "CAS", "Computeralgebrasystem"

    fach = models.ForeignKey(
        Fach, verbose_name="Fach", on_delete=models.PROTECT, related_name="klausuren"
    )
    jahr = models.PositiveSmallIntegerField("Jahr")
    kursart = models.CharField("Kursart", max_length=2, choices=Kursart.choices)
    termin = models.CharField("Termin", max_length=20, choices=Termin.choices)
    variante = models.CharField("Variante", max_length=50, blank=True, default="")
    titel = models.CharField("Titel", max_length=200)
    hilfsmittel = models.CharField("Hilfsmittel", max_length=3, choices=Hilfsmittel.choices)
    pdf = models.FileField("Klausur-PDF", upload_to="klausuren/")
    erwartungshorizont_pdf = models.FileField(
        "Erwartungshorizont-PDF", upload_to="erwartungshorizonte/", null=True, blank=True
    )
    importprotokoll = models.ForeignKey(
        "importer.Importprotokoll",
        verbose_name="Importprotokoll",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="klausuren",
    )
    status = models.CharField(
        "Status", max_length=20, choices=Status.choices, default=Status.FREIGEGEBEN
    )
    ersteller = models.ForeignKey(
        "accounts.Lehrkraft",
        verbose_name="Ersteller",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="erstellte_klausuren",
    )
    ablehnungskommentar = models.TextField("Ablehnungskommentar", blank=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    objects = KlausurQuerySet.as_manager()

    class Meta:
        verbose_name = "Klausur"
        verbose_name_plural = "Klausuren"
        constraints = [
            models.UniqueConstraint(
                fields=["fach", "jahr", "kursart", "termin", "variante"],
                name="eindeutige_klausur",
            ),
        ]
        ordering = ["-jahr", "fach"]

    def __str__(self):
        return f"{self.titel} ({self.fach.kuerzel} {self.jahr} {self.kursart})"


class AufgabeQuerySet(models.QuerySet):
    def sichtbar_fuer(self, request):
        return self.filter(klausur__in=Klausur.objects.sichtbar_fuer(request))


class Aufgabe(models.Model):
    class Pruefungsteil(models.TextChoices):
        HILFSMITTELFREI = "hilfsmittelfrei", "Hilfsmittelfrei"
        MIT_HILFSMITTELN = "mit_hilfsmitteln", "Mit Hilfsmitteln"

    class Aufgabenbereich(models.TextChoices):
        PFLICHT = "pflicht", "Pflicht"
        WAHLPFLICHT = "wahlpflicht", "Wahlpflicht"
        KEINE_ANGABE = "keine_angabe", "Keine Angabe"

    klausur = models.ForeignKey(
        Klausur, verbose_name="Klausur", on_delete=models.CASCADE, related_name="aufgaben"
    )
    nummer = models.PositiveSmallIntegerField("Nummer")
    kontext = models.CharField("Kontext", max_length=200, blank=True)
    # Beim Admin-Import immer aus der JSON-Datei gesetzt (Pflichtfeld dort). Im
    # Lehrkraft-Editor dagegen zunächst leer und wird automatisch aus den Bereichen der
    # Aufgabe abgeleitet (Min/Max der Seiten), sobald die Lehrkraft Bereiche markiert hat.
    seite_von = models.PositiveSmallIntegerField("Seite von", null=True, blank=True)
    seite_bis = models.PositiveSmallIntegerField("Seite bis", null=True, blank=True)
    pruefungsteil = models.CharField("Prüfungsteil", max_length=20, choices=Pruefungsteil.choices)
    aufgabenbereich = models.CharField(
        "Aufgabenbereich",
        max_length=20,
        choices=Aufgabenbereich.choices,
        default=Aufgabenbereich.KEINE_ANGABE,
    )

    objects = AufgabeQuerySet.as_manager()

    class Meta:
        verbose_name = "Aufgabe"
        verbose_name_plural = "Aufgaben"
        constraints = [
            models.UniqueConstraint(fields=["klausur", "nummer"], name="eindeutige_aufgabennummer"),
        ]
        ordering = ["klausur", "nummer"]

    def __str__(self):
        return f"Aufgabe {self.nummer} ({self.klausur})"


class TeilaufgabeQuerySet(models.QuerySet):
    def sichtbar_fuer(self, request):
        return self.filter(aufgabe__in=Aufgabe.objects.sichtbar_fuer(request))

    def in_thema(self, kennung):
        """Teilaufgaben, deren Thema `kennung` selbst ist oder einem seiner
        Unterthemen entspricht. Die Kennung kodiert den Pfad im Themenbaum
        (z. B. `analysis.diff.wendepunkt`), daher genügt ein Präfix-Vergleich
        statt einer rekursiven Baumabfrage."""
        return self.filter(
            models.Q(themen__kennung=kennung) | models.Q(themen__kennung__startswith=f"{kennung}.")
        ).distinct()


class Teilaufgabe(models.Model):
    class Anforderungsbereich(models.TextChoices):
        I = "I", "Anforderungsbereich I"  # noqa: E741
        II = "II", "Anforderungsbereich II"
        III = "III", "Anforderungsbereich III"

    aufgabe = models.ForeignKey(
        Aufgabe, verbose_name="Aufgabe", on_delete=models.CASCADE, related_name="teilaufgaben"
    )
    bezeichnung = models.CharField("Bezeichnung", max_length=20)
    # Beim Admin-Import immer gesetzt (Pflichtfelder dort). Im Lehrkraft-Editor zunächst
    # leer: Text wird aus den Bereichen der Teilaufgabe extrahiert, Seite daraus
    # abgeleitet, Anforderungsbereich bestenfalls per Operatoren-Vorschlag vorbefüllt,
    # endgültig aber erst von der Lehrkraft bestätigt (siehe CLAUDE.md, Abschnitt
    # Lehrkraft-Editor).
    text = models.TextField("Text", blank=True)
    seite = models.PositiveSmallIntegerField("Seite", null=True, blank=True)
    punkte = models.PositiveSmallIntegerField("Punkte", null=True, blank=True)
    themen = models.ManyToManyField(
        Thema, verbose_name="Themen", related_name="teilaufgaben", blank=True
    )
    anforderungsbereich = models.CharField(
        "Anforderungsbereich", max_length=3, choices=Anforderungsbereich.choices, blank=True
    )
    operatoren = ArrayField(
        models.CharField(max_length=50), verbose_name="Operatoren", default=list, blank=True
    )
    begruendung = models.TextField("Begründung der Zuordnung", blank=True)
    # Wird erst mit der Suche in Phase 5 befüllt/aktuell gehalten; Spalte liegt
    # schon jetzt vor, damit das Datenmodell vollständig ist (siehe CLAUDE.md).
    such_vektor = SearchVectorField(null=True, editable=False)

    objects = TeilaufgabeQuerySet.as_manager()

    class Meta:
        verbose_name = "Teilaufgabe"
        verbose_name_plural = "Teilaufgaben"
        constraints = [
            models.UniqueConstraint(
                fields=["aufgabe", "bezeichnung"], name="eindeutige_teilaufgabe"
            ),
        ]
        indexes = [GinIndex(fields=["such_vektor"])]
        ordering = ["aufgabe", "bezeichnung"]

    def __str__(self):
        return f"{self.bezeichnung} ({self.aufgabe})"


class Bereich(models.Model):
    """Markierter Bereich auf einer PDF-Seite im Lehrkraft-Editor (CLAUDE.md, Abschnitt
    Lehrkraft-Editor). Gehört zu genau einer Aufgabe oder einer Teilaufgabe – nie beidem,
    nie keinem. Koordinaten normiert auf 0–1 relativ zur Seitengröße, damit sie unabhängig
    von der Darstellungsgröße im Browser sind. Entsteht nur im Lehrkraft-Editor, nicht
    beim Admin-Import."""

    aufgabe = models.ForeignKey(
        Aufgabe,
        verbose_name="Aufgabe",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="bereiche",
    )
    teilaufgabe = models.ForeignKey(
        Teilaufgabe,
        verbose_name="Teilaufgabe",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="bereiche",
    )
    seite = models.PositiveSmallIntegerField("Seite")
    x0 = models.FloatField("x0")
    y0 = models.FloatField("y0")
    x1 = models.FloatField("x1")
    y1 = models.FloatField("y1")

    class Meta:
        verbose_name = "Bereich"
        verbose_name_plural = "Bereiche"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(aufgabe__isnull=False, teilaufgabe__isnull=True)
                    | models.Q(aufgabe__isnull=True, teilaufgabe__isnull=False)
                ),
                name="bereich_genau_ein_ziel",
            ),
        ]
        ordering = ["seite"]

    def __str__(self):
        ziel = self.aufgabe or self.teilaufgabe
        return f"Bereich auf Seite {self.seite} ({ziel})"


class NachschreibZugriff(models.Model):
    """Protokoll jedes Abrufs einer Nachschreibklausur durch eine Lehrkraft
    (siehe CLAUDE.md, Abschnitt Nachschreibklausuren). Der eigentliche
    Logging-Aufruf erfolgt erst mit der Klausuransicht in Phase 5."""

    lehrkraft = models.ForeignKey(
        "accounts.Lehrkraft",
        verbose_name="Lehrkraft",
        on_delete=models.PROTECT,
        related_name="nachschreib_zugriffe",
    )
    klausur = models.ForeignKey(
        Klausur,
        verbose_name="Klausur",
        on_delete=models.PROTECT,
        related_name="nachschreib_zugriffe",
    )
    zeitpunkt = models.DateTimeField("Zeitpunkt", auto_now_add=True)

    class Meta:
        verbose_name = "Nachschreib-Zugriff"
        verbose_name_plural = "Nachschreib-Zugriffe"
        ordering = ["-zeitpunkt"]

    def __str__(self):
        return f"{self.lehrkraft} → {self.klausur} ({self.zeitpunkt:%Y-%m-%d %H:%M})"
