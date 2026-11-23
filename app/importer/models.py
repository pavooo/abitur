from django.db import models


class Importprotokoll(models.Model):
    class Ergebnis(models.TextChoices):
        ERFOLGREICH = "erfolgreich", "Erfolgreich"
        FEHLGESCHLAGEN = "fehlgeschlagen", "Fehlgeschlagen"

    lehrkraft = models.ForeignKey(
        "accounts.Lehrkraft",
        verbose_name="Lehrkraft",
        on_delete=models.PROTECT,
        related_name="importprotokolle",
    )
    zeitpunkt = models.DateTimeField("Zeitpunkt", auto_now_add=True)
    paketname = models.CharField("Paketname", max_length=255)
    ergebnis = models.CharField("Ergebnis", max_length=20, choices=Ergebnis.choices)
    anzahl_neu = models.PositiveSmallIntegerField("Anzahl neu", default=0)
    anzahl_aktualisiert = models.PositiveSmallIntegerField("Anzahl aktualisiert", default=0)
    fehlermeldung = models.TextField("Fehlermeldung", blank=True)

    class Meta:
        verbose_name = "Importprotokoll"
        verbose_name_plural = "Importprotokolle"
        ordering = ["-zeitpunkt"]

    def __str__(self):
        return f"{self.paketname} ({self.zeitpunkt:%Y-%m-%d %H:%M}, {self.get_ergebnis_display()})"
