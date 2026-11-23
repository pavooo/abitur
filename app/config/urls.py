from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("accounts.urls")),
    path("archiv/", include("archiv.urls")),
    path("adminbereich/", include("adminbereich.urls")),
    # Nicht verlinkter, nicht erratbarer Pfad – nur für Notfälle/Superuser (siehe CLAUDE.md).
    path(settings.ADMIN_URL_PFAD, admin.site.urls),
]
