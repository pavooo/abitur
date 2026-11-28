from django.urls import path

from . import views

app_name = "editor"

urlpatterns = [
    path("meine-klausuren/", views.meine_klausuren, name="meine_klausuren"),
    path("klausuren/neu/", views.schritt1, name="schritt1_neu"),
    path("klausuren/<int:pk>/schritt-1/", views.schritt1, name="schritt1"),
    path("klausuren/<int:pk>/schritt-2/", views.schritt2, name="schritt2"),
    path("klausuren/<int:pk>/schritt-3/", views.schritt3, name="schritt3"),
    path("klausuren/<int:pk>/schritt-4/", views.schritt4, name="schritt4"),
    path("klausuren/<int:pk>/aufgaben/neu/", views.aufgabe_erstellen, name="aufgabe_erstellen"),
    path(
        "klausuren/<int:pk>/aufgaben/<int:aufgabe_pk>/loeschen/",
        views.aufgabe_loeschen,
        name="aufgabe_loeschen",
    ),
    path("klausuren/<int:pk>/bereiche/neu/", views.bereich_erstellen, name="bereich_erstellen"),
    path(
        "klausuren/<int:pk>/bereiche/<int:bereich_pk>/",
        views.bereich_aktualisieren,
        name="bereich_aktualisieren",
    ),
    path(
        "klausuren/<int:pk>/bereiche/<int:bereich_pk>/loeschen/",
        views.bereich_loeschen,
        name="bereich_loeschen",
    ),
    path(
        "klausuren/<int:pk>/teilaufgaben-panel/",
        views.teilaufgaben_panel_fragment,
        name="teilaufgaben_panel_fragment",
    ),
    path(
        "klausuren/<int:pk>/aufgaben/<int:aufgabe_pk>/teilaufgaben/neu/",
        views.teilaufgabe_erstellen,
        name="teilaufgabe_erstellen",
    ),
    path(
        "klausuren/<int:pk>/teilaufgaben/<int:teilaufgabe_pk>/",
        views.teilaufgabe_aktualisieren,
        name="teilaufgabe_aktualisieren",
    ),
    path(
        "klausuren/<int:pk>/teilaufgaben/<int:teilaufgabe_pk>/loeschen/",
        views.teilaufgabe_loeschen,
        name="teilaufgabe_loeschen",
    ),
    path("klausuren/<int:pk>/option-c/", views.option_c, name="option_c"),
    path("option-c/format/", views.option_c_format, name="option_c_format"),
]
