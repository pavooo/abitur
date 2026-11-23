from django.contrib import admin

from .models import Importprotokoll


@admin.register(Importprotokoll)
class ImportprotokollAdmin(admin.ModelAdmin):
    list_display = [
        "paketname",
        "lehrkraft",
        "zeitpunkt",
        "ergebnis",
        "anzahl_neu",
        "anzahl_aktualisiert",
    ]
    list_filter = ["ergebnis"]
    readonly_fields = [
        "lehrkraft",
        "zeitpunkt",
        "paketname",
        "ergebnis",
        "anzahl_neu",
        "anzahl_aktualisiert",
        "fehlermeldung",
    ]
