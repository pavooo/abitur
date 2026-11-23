from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.LoginWaehlenView.as_view(), name="login_waehlen"),
    path("lehrkraft/login/", views.LehrkraftLoginView.as_view(), name="lehrkraft_login"),
    path("lehrkraft/registrieren/", views.RegistrierungView.as_view(), name="registrieren"),
    path("lehrkraft/start/", views.lehrkraft_startseite, name="lehrkraft_startseite"),
    path("code/", views.ZugangscodeLoginView.as_view(), name="code_login"),
    path("sus/start/", views.sus_startseite, name="sus_startseite"),
    path(
        "logout/",
        LogoutView.as_view(next_page="accounts:login_waehlen"),
        name="logout",
    ),
]
