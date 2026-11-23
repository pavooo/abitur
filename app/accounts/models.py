import secrets
import string

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1I")


def _generiere_klartext_code(laenge=10):
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(laenge))


class LehrkraftManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("E-Mail-Adresse ist erforderlich.")
        email = self.normalize_email(email)
        lehrkraft = self.model(email=email, **extra_fields)
        lehrkraft.set_password(password)
        lehrkraft.save(using=self._db)
        return lehrkraft

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("status", Lehrkraft.Status.AKTIV)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser muss is_superuser=True haben.")
        return self.create_user(email, password, **extra_fields)


class Lehrkraft(AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        AUSSTEHEND = "ausstehend", "Ausstehend"
        AKTIV = "aktiv", "Aktiv"
        GESPERRT = "gesperrt", "Gesperrt"

    email = models.EmailField("E-Mail-Adresse", unique=True)
    vorname = models.CharField("Vorname", max_length=100, blank=True)
    nachname = models.CharField("Nachname", max_length=100, blank=True)
    status = models.CharField(
        "Status", max_length=20, choices=Status.choices, default=Status.AUSSTEHEND
    )
    ist_admin = models.BooleanField("Admin-Recht", default=False)
    faecher = models.ManyToManyField(
        "archiv.Fach", verbose_name="Fächer", related_name="lehrkraefte", blank=True
    )
    erstellt_am = models.DateTimeField(auto_now_add=True)

    objects = LehrkraftManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Lehrkraft"
        verbose_name_plural = "Lehrkräfte"
        ordering = ["email"]

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        """Immer True: ModelBackend.authenticate() lehnt inaktive Nutzer sonst schon vor
        confirm_login_allowed() ab, sodass unsere statusspezifischen Fehlermeldungen
        (ausstehend/gesperrt) nie angezeigt würden. Die eigentliche Freigabeprüfung
        übernehmen LehrkraftAuthenticationForm.confirm_login_allowed() beim Login und
        LehrkraftSessionMiddleware für bereits bestehende Sessions."""
        return True

    @property
    def is_staff(self):
        """Zugriff auf das (verborgene) Django-Admin bleibt Superusern vorbehalten."""
        return self.is_superuser

    @property
    def name(self):
        if self.vorname or self.nachname:
            return f"{self.vorname} {self.nachname}".strip()
        return self.email


class Zugangscode(models.Model):
    fach = models.ForeignKey(
        "archiv.Fach", verbose_name="Fach", on_delete=models.PROTECT, related_name="zugangscodes"
    )
    bezeichnung = models.CharField("Bezeichnung", max_length=200)
    code_hash = models.CharField(max_length=255)
    ablaufdatum = models.DateField("Ablaufdatum")
    gesperrt = models.BooleanField("Gesperrt", default=False)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Zugangscode"
        verbose_name_plural = "Zugangscodes"
        ordering = ["-erstellt_am"]

    def __str__(self):
        return f"{self.bezeichnung} ({self.fach.kuerzel})"

    def ist_gueltig(self):
        return not self.gesperrt and self.ablaufdatum >= timezone.localdate()

    def code_setzen(self, klartext_code):
        self.code_hash = make_password(klartext_code)

    def code_pruefen(self, klartext_code):
        return check_password(klartext_code, self.code_hash)

    @classmethod
    def erstellen(cls, *, fach, bezeichnung, ablaufdatum):
        klartext_code = _generiere_klartext_code()
        zugangscode = cls(fach=fach, bezeichnung=bezeichnung, ablaufdatum=ablaufdatum)
        zugangscode.code_setzen(klartext_code)
        zugangscode.save()
        return zugangscode, klartext_code

    @classmethod
    def finde_gueltigen_code(cls, klartext_code):
        heute = timezone.localdate()
        kandidaten = cls.objects.filter(gesperrt=False, ablaufdatum__gte=heute)
        for kandidat in kandidaten:
            if kandidat.code_pruefen(klartext_code):
                return kandidat
        return None
