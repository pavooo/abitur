from django.urls import path

from . import views

app_name = "archiv"

urlpatterns = [
    path("suche/", views.suche, name="suche"),
    path("themen/", views.themenbrowser, name="themenbrowser"),
    path("klausuren/<int:pk>/", views.klausur_detail, name="klausur_detail"),
    path("klausuren/<int:pk>/datei/<str:art>/", views.klausur_datei, name="klausur_datei"),
    path(
        "klausuren/<int:pk>/vorschaubild/<int:seite>/",
        views.vorschaubild,
        name="vorschaubild",
    ),
    path(
        "nachschreibmodus/umschalten/",
        views.nachschreibmodus_umschalten,
        name="nachschreibmodus_umschalten",
    ),
]
