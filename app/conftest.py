import pytest


@pytest.fixture(autouse=True)
def _media_root_in_tmp_verzeichnis(settings, tmp_path):
    """Verhindert, dass Tests mit FileField-Uploads echte Dateien im
    Projekt-`media/`-Verzeichnis hinterlassen (DB-Rollback löscht keine
    Dateien von der Platte)."""
    settings.MEDIA_ROOT = tmp_path
