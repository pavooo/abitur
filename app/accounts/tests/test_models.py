import datetime

import pytest
from archiv.models import Fach
from django.utils import timezone

from accounts.models import Lehrkraft, Zugangscode


@pytest.fixture
def fach(db):
    return Fach.objects.create(name="Mathematik", kuerzel="M")


@pytest.mark.django_db
class TestLehrkraft:
    def test_create_user_setzt_status_ausstehend(self):
        lehrkraft = Lehrkraft.objects.create_user(email="neu@schule.de", password="s3hrGeheim!")
        assert lehrkraft.status == Lehrkraft.Status.AUSSTEHEND

    def test_create_superuser_ist_aktiv_und_staff(self):
        superuser = Lehrkraft.objects.create_superuser(
            email="admin@schule.de", password="s3hrGeheim!"
        )
        assert superuser.is_active is True
        assert superuser.is_staff is True
        assert superuser.is_superuser is True

    def test_nicht_superuser_hat_keinen_staff_zugriff(self):
        lehrkraft = Lehrkraft.objects.create_user(
            email="lehrkraft@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        assert lehrkraft.is_staff is False


@pytest.mark.django_db
class TestZugangscode:
    def test_erstellen_liefert_pruefbaren_klartext_code(self, fach):
        zugangscode, klartext_code = Zugangscode.erstellen(
            fach=fach,
            bezeichnung="Mathe-LK Abi 2027",
            ablaufdatum=timezone.localdate() + datetime.timedelta(days=30),
        )
        assert zugangscode.code_pruefen(klartext_code) is True
        assert zugangscode.code_pruefen("falscher-code") is False
        # Der Klartext-Code wird nirgends im Modell gespeichert.
        assert klartext_code not in zugangscode.code_hash

    def test_ist_gueltig_false_bei_abgelaufenem_code(self, fach):
        zugangscode, _ = Zugangscode.erstellen(
            fach=fach,
            bezeichnung="Alt",
            ablaufdatum=timezone.localdate() - datetime.timedelta(days=1),
        )
        assert zugangscode.ist_gueltig() is False

    def test_ist_gueltig_false_bei_gesperrtem_code(self, fach):
        zugangscode, _ = Zugangscode.erstellen(
            fach=fach,
            bezeichnung="Gesperrt",
            ablaufdatum=timezone.localdate() + datetime.timedelta(days=30),
        )
        zugangscode.gesperrt = True
        zugangscode.save()
        assert zugangscode.ist_gueltig() is False

    def test_finde_gueltigen_code_findet_nur_gueltige_codes(self, fach):
        _gueltig, klartext_gueltig = Zugangscode.erstellen(
            fach=fach,
            bezeichnung="Gültig",
            ablaufdatum=timezone.localdate() + datetime.timedelta(days=30),
        )
        abgelaufen, klartext_abgelaufen = Zugangscode.erstellen(
            fach=fach,
            bezeichnung="Abgelaufen",
            ablaufdatum=timezone.localdate() - datetime.timedelta(days=1),
        )

        gefunden = Zugangscode.finde_gueltigen_code(klartext_gueltig)
        assert gefunden == _gueltig
        assert Zugangscode.finde_gueltigen_code(klartext_abgelaufen) is None
        assert Zugangscode.finde_gueltigen_code("existiert-nicht") is None
