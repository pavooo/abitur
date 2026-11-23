import json

import jsonschema
from django.conf import settings

SCHEMA_VERSION = "1.0"

_SCHEMA_DIR = settings.REPO_ROOT / "schema"


def _schema_laden(dateiname):
    return json.loads((_SCHEMA_DIR / dateiname).read_text(encoding="utf-8"))


MANIFEST_SCHEMA = _schema_laden("manifest.schema.json")
TAXONOMIE_SCHEMA = _schema_laden("taxonomie.schema.json")
KLAUSUR_SCHEMA = _schema_laden("klausur.schema.json")


def validiere_gegen_schema(instanz, schema):
    """Gibt eine Liste lesbarer Fehlermeldungen zurück (leer, wenn gültig)."""
    validator = jsonschema.Draft202012Validator(schema)
    fehler = sorted(validator.iter_errors(instanz), key=lambda e: list(map(str, e.path)))
    return [_fehler_lesbar(f) for f in fehler]


def _fehler_lesbar(fehler):
    pfad = ".".join(str(teil) for teil in fehler.path) or "(Wurzel)"
    return f"{pfad}: {fehler.message}"
