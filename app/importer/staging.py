import secrets
import shutil
from pathlib import Path

from django.conf import settings


def neues_token() -> str:
    return secrets.token_urlsafe(16)


def staging_verzeichnis(token: str) -> Path:
    return Path(settings.IMPORT_STAGING_ROOT) / token


def staging_aufraeumen(token: str) -> None:
    verzeichnis = staging_verzeichnis(token)
    if verzeichnis.exists():
        shutil.rmtree(verzeichnis)
