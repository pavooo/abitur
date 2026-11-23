from archiv.views import suche as archiv_suche
from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_client_ip_address
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from .decorators import sus_erforderlich
from .forms import LehrkraftAuthenticationForm, LehrkraftRegistrierungForm, ZugangscodeLoginForm
from .models import Zugangscode

# Konstanter Platzhalter-Bezeichner für Axes bei der Code-Eingabe: verhindert,
# dass eingegebene (ggf. falsche) Zugangscodes jemals im Axes-Protokoll landen.
CODE_LOGIN_AXES_USERNAME = "sus-code-login"


class LoginWaehlenView(TemplateView):
    template_name = "accounts/login_waehlen.html"


class LehrkraftLoginView(LoginView):
    template_name = "accounts/lehrkraft_login.html"
    authentication_form = LehrkraftAuthenticationForm

    def form_valid(self, form):
        self.request.session.pop("sus_zugangscode_id", None)
        return super().form_valid(form)

    def get_success_url(self):
        if self.request.user.ist_admin:
            return reverse("adminbereich:dashboard")
        return reverse("accounts:lehrkraft_startseite")


class RegistrierungView(FormView):
    template_name = "accounts/registrieren.html"
    form_class = LehrkraftRegistrierungForm
    success_url = "/"

    def get_success_url(self):
        return reverse("accounts:lehrkraft_login")

    def form_valid(self, form):
        _lehrkraft, wird_erster_admin = form.save()
        if wird_erster_admin:
            messages.success(
                self.request,
                "Willkommen! Da Sie die erste Registrierung sind, wurden Sie automatisch "
                "als Admin freigeschaltet. Sie können sich jetzt anmelden.",
            )
        else:
            messages.success(
                self.request,
                "Registrierung erfolgreich. Ihr Konto muss noch von einem Admin "
                "freigeschaltet werden, bevor Sie sich anmelden können.",
            )
        return redirect(self.get_success_url())


class ZugangscodeLoginView(FormView):
    template_name = "accounts/code_login.html"
    form_class = ZugangscodeLoginForm

    def get_success_url(self):
        return reverse("accounts:sus_startseite")

    def form_valid(self, form):
        credentials = {"username": CODE_LOGIN_AXES_USERNAME}
        if AxesProxyHandler.is_locked(self.request, credentials):
            form.add_error(None, "Zu viele Fehlversuche. Bitte versuchen Sie es später erneut.")
            return self.form_invalid(form)

        code = form.cleaned_data["code"].strip()
        zugangscode = Zugangscode.finde_gueltigen_code(code)
        if zugangscode is None:
            AxesProxyHandler.user_login_failed(
                sender=self.__class__, credentials=credentials, request=self.request
            )
            form.add_error(None, "Zugangscode ungültig oder abgelaufen.")
            return self.form_invalid(form)

        AxesProxyHandler.reset_attempts(ip_address=get_client_ip_address(self.request))
        auth_logout(self.request)
        self.request.session["sus_zugangscode_id"] = zugangscode.pk
        return redirect(self.get_success_url())


@login_required
def lehrkraft_startseite(request):
    return archiv_suche(request)


@sus_erforderlich
def sus_startseite(request):
    return archiv_suche(request)
