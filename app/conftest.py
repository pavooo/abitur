import pytest


@pytest.fixture(autouse=True)
def _dateisystem_pfade_in_tmp_verzeichnis(settings, tmp_path):
    """Verhindert, dass Tests mit FileField-Uploads oder Import-Staging echte
    Dateien im Projektverzeichnis hinterlassen (DB-Rollback löscht keine
    Dateien von der Platte, und ein nie bestätigter Import-Upload würde sein
    Staging-Verzeichnis sonst dauerhaft behalten)."""
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.IMPORT_STAGING_ROOT = tmp_path / "import_staging"
