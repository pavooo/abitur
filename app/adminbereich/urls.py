from django.urls import path

from . import views

app_name = "adminbereich"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("lehrkraefte/", views.lehrkraft_liste, name="lehrkraft_liste"),
    path("lehrkraefte/<int:pk>/", views.lehrkraft_detail, name="lehrkraft_detail"),
    path("faecher/", views.fach_liste, name="fach_liste"),
    path("codes/", views.zugangscode_liste, name="zugangscode_liste"),
    path(
        "codes/<int:pk>/sperren-umschalten/",
        views.zugangscode_sperren_umschalten,
        name="zugangscode_sperren_umschalten",
    ),
    path(
        "codes/<int:pk>/neu-generieren/",
        views.zugangscode_neu_generieren,
        name="zugangscode_neu_generieren",
    ),
    path("import/", views.import_hochladen, name="import_hochladen"),
    path("import/bestaetigen/", views.import_bestaetigen, name="import_bestaetigen"),
    path("import/protokoll/", views.import_protokoll_liste, name="import_protokoll_liste"),
    path(
        "nachschreibklausuren/protokoll/",
        views.nachschreib_protokoll_liste,
        name="nachschreib_protokoll_liste",
    ),
]
