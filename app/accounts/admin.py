from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Lehrkraft, Zugangscode


@admin.register(Lehrkraft)
class LehrkraftAdmin(UserAdmin):
    model = Lehrkraft
    list_display = ["email", "vorname", "nachname", "status", "ist_admin", "is_superuser"]
    list_filter = ["status", "ist_admin", "is_superuser"]
    search_fields = ["email", "vorname", "nachname"]
    ordering = ["email"]
    filter_horizontal = ["faecher", "groups", "user_permissions"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Persönliche Daten", {"fields": ("vorname", "nachname")}),
        ("Status", {"fields": ("status", "ist_admin", "faecher")}),
        ("Berechtigungen", {"fields": ("is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = ((None, {"fields": ("email", "password1", "password2")}),)


@admin.register(Zugangscode)
class ZugangscodeAdmin(admin.ModelAdmin):
    list_display = ["bezeichnung", "fach", "ablaufdatum", "gesperrt", "erstellt_am"]
    list_filter = ["fach", "gesperrt"]
    readonly_fields = ["code_hash", "erstellt_am"]
