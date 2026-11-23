from config.forms import TailwindFormMixin
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import Lehrkraft


class LehrkraftAuthenticationForm(TailwindFormMixin, AuthenticationForm):
    def confirm_login_allowed(self, user):
        if user.status == Lehrkraft.Status.AUSSTEHEND:
            raise ValidationError(
                "Ihr Konto wartet noch auf die Freischaltung durch einen Admin.",
                code="ausstehend",
            )
        if user.status == Lehrkraft.Status.GESPERRT:
            raise ValidationError(
                "Ihr Konto wurde gesperrt. Bitte wenden Sie sich an einen Admin.",
                code="gesperrt",
            )
        super().confirm_login_allowed(user)


class LehrkraftRegistrierungForm(TailwindFormMixin, forms.ModelForm):
    passwort = forms.CharField(label="Passwort", widget=forms.PasswordInput, strip=False)
    passwort_wiederholen = forms.CharField(
        label="Passwort wiederholen", widget=forms.PasswordInput, strip=False
    )

    class Meta:
        model = Lehrkraft
        fields = ["email", "vorname", "nachname"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        return Lehrkraft.objects.normalize_email(email)

    def clean(self):
        cleaned_data = super().clean()
        passwort = cleaned_data.get("passwort")
        passwort_wiederholen = cleaned_data.get("passwort_wiederholen")
        if passwort and passwort_wiederholen and passwort != passwort_wiederholen:
            self.add_error("passwort_wiederholen", "Die Passwörter stimmen nicht überein.")
        if passwort:
            try:
                password_validation.validate_password(passwort)
            except ValidationError as error:
                self.add_error("passwort", error)
        return cleaned_data

    def save(self, commit=True):
        lehrkraft = super().save(commit=False)
        lehrkraft.set_password(self.cleaned_data["passwort"])
        wird_erster_admin = not Lehrkraft.objects.exists()
        if wird_erster_admin:
            lehrkraft.status = Lehrkraft.Status.AKTIV
            lehrkraft.ist_admin = True
        if commit:
            lehrkraft.save()
        return lehrkraft, wird_erster_admin


class ZugangscodeLoginForm(TailwindFormMixin, forms.Form):
    code = forms.CharField(label="Zugangscode", max_length=64, strip=True)
