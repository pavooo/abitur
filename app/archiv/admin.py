from django.contrib import admin

from .models import Aufgabe, Fach, Klausur, NachschreibZugriff, Teilaufgabe, Thema


@admin.register(Fach)
class FachAdmin(admin.ModelAdmin):
    list_display = ["name", "kuerzel"]
    search_fields = ["name", "kuerzel"]


@admin.register(Thema)
class ThemaAdmin(admin.ModelAdmin):
    list_display = ["kennung", "name", "fach", "eltern", "kursniveau"]
    list_filter = ["fach", "kursniveau"]
    search_fields = ["kennung", "name"]


class AufgabeInline(admin.TabularInline):
    model = Aufgabe
    extra = 0


@admin.register(Klausur)
class KlausurAdmin(admin.ModelAdmin):
    list_display = ["titel", "fach", "jahr", "kursart", "termin", "variante", "hilfsmittel"]
    list_filter = ["fach", "jahr", "kursart", "termin", "hilfsmittel"]
    search_fields = ["titel"]
    inlines = [AufgabeInline]


class TeilaufgabeInline(admin.TabularInline):
    model = Teilaufgabe
    extra = 0


@admin.register(Aufgabe)
class AufgabeAdmin(admin.ModelAdmin):
    list_display = ["klausur", "nummer", "kontext", "pruefungsteil", "aufgabenbereich"]
    list_filter = ["klausur__fach", "pruefungsteil", "aufgabenbereich"]
    inlines = [TeilaufgabeInline]


@admin.register(Teilaufgabe)
class TeilaufgabeAdmin(admin.ModelAdmin):
    list_display = ["bezeichnung", "aufgabe", "anforderungsbereich", "punkte"]
    list_filter = ["anforderungsbereich"]
    filter_horizontal = ["themen"]


@admin.register(NachschreibZugriff)
class NachschreibZugriffAdmin(admin.ModelAdmin):
    list_display = ["lehrkraft", "klausur", "zeitpunkt"]
    list_filter = ["lehrkraft"]
    readonly_fields = ["lehrkraft", "klausur", "zeitpunkt"]
