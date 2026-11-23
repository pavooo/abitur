import pytest
from accounts.models import Lehrkraft
from archiv.models import Klausur
from django.core.management import call_command
from django.core.management.base import CommandError

from importer.models import Importprotokoll

from .conftest import klausur_json, manifest_fuer, schreibe_paket_zip


@pytest.mark.django_db
class TestImportPaketCommand:
    def test_erfolgreicher_import(self, tmp_path, fach_mathe, admin_lehrkraft):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        )

        call_command("import_paket", str(zip_pfad), "--lehrkraft", admin_lehrkraft.email)

        assert Klausur.objects.filter(fach=fach_mathe).count() == 1
        assert Importprotokoll.objects.filter(lehrkraft=admin_lehrkraft).exists()

    def test_bricht_bei_fehlern_in_der_vorschau_ab(self, tmp_path, fach_mathe, admin_lehrkraft):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M", themen=["unbekannt.kennung"])],
        )

        with pytest.raises(CommandError, match="abgebrochen"):
            call_command("import_paket", str(zip_pfad), "--lehrkraft", admin_lehrkraft.email)

        assert Klausur.objects.filter(fach=fach_mathe).count() == 0

    def test_unbekannte_lehrkraft_email_bricht_ab(self, tmp_path, fach_mathe):
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        )

        with pytest.raises(CommandError, match="Keine Lehrkraft"):
            call_command("import_paket", str(zip_pfad), "--lehrkraft", "unbekannt@schule.de")

    def test_lehrkraft_ohne_admin_recht_bricht_ab(self, tmp_path, fach_mathe):
        lehrkraft = Lehrkraft.objects.create_user(
            email="normal@schule.de", password="s3hrGeheim!", status=Lehrkraft.Status.AKTIV
        )
        zip_pfad = schreibe_paket_zip(
            tmp_path / "paket.zip",
            manifest=manifest_fuer("M"),
            klausuren=[klausur_json(id="M-2024-LK-HT-A", fach="M")],
        )

        with pytest.raises(CommandError, match="kein Admin-Recht"):
            call_command("import_paket", str(zip_pfad), "--lehrkraft", lehrkraft.email)
