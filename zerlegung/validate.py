#!/usr/bin/env python3
"""Validiert eine einzelne JSON-Datei oder ein ganzes Import-Paket (ZIP) gegen
die Schemata in `schema/` – dieselben, die auch die App beim Import nutzt.

Eigenständiges Skript ohne Django-Abhängigkeit (zerlegung/ ist nicht Teil der
Web-App). Prüft nur die JSON-Struktur, keine fachlichen/DB-Regeln (z. B. ob ein
Fach oder eine Themen-Kennung bereits existiert – das prüft die App beim Import).

Nutzung:
    python zerlegung/validate.py <pfad-zu-datei.json> [--typ manifest|taxonomie|klausur]
    python zerlegung/validate.py <pfad-zu-paket.zip>
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"


def schema_laden(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def validiere(daten: dict, schema: dict) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    fehler = sorted(validator.iter_errors(daten), key=lambda e: list(map(str, e.path)))
    return [f"{'.'.join(str(t) for t in f.path) or '(Wurzel)'}: {f.message}" for f in fehler]


def typ_erraten(daten: dict) -> str:
    if "themen" in daten:
        return "taxonomie"
    if "aufgaben" in daten:
        return "klausur"
    return "manifest"


def validiere_json_datei(pfad: Path, typ: str | None) -> list[str]:
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Kein gültiges JSON: {exc}"]

    typ = typ or typ_erraten(daten)
    schema = schema_laden(typ)
    return validiere(daten, schema)


def validiere_paket(pfad: Path) -> list[str]:
    fehler = []
    with zipfile.ZipFile(pfad) as zf:
        namen = set(zf.namelist())

        if "manifest.json" not in namen:
            return ["Paket enthält keine manifest.json."]
        manifest = json.loads(zf.read("manifest.json"))
        for f in validiere(manifest, schema_laden("manifest")):
            fehler.append(f"manifest.json: {f}")

        if "taxonomie.json" in namen:
            taxonomie = json.loads(zf.read("taxonomie.json"))
            for f in validiere(taxonomie, schema_laden("taxonomie")):
                fehler.append(f"taxonomie.json: {f}")

        klausur_schema = schema_laden("klausur")
        for name in sorted(namen):
            if not (name.startswith("klausuren/") and name.endswith(".json")):
                continue
            klausur = json.loads(zf.read(name))
            for f in validiere(klausur, klausur_schema):
                fehler.append(f"{name}: {f}")

            klausur_id = klausur.get("id") or Path(name).stem
            if f"dateien/{klausur_id}.pdf" not in namen:
                fehler.append(f"{name}: zugehörige Datei dateien/{klausur_id}.pdf fehlt im Paket.")

    return fehler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pfad", type=Path)
    parser.add_argument("--typ", choices=["manifest", "taxonomie", "klausur"], default=None)
    args = parser.parse_args()

    if not args.pfad.exists():
        print(f"Datei nicht gefunden: {args.pfad}", file=sys.stderr)
        return 2

    if args.pfad.suffix == ".zip":
        fehler = validiere_paket(args.pfad)
    else:
        fehler = validiere_json_datei(args.pfad, args.typ)

    if fehler:
        print(f"{len(fehler)} Fehler in {args.pfad}:")
        for f in fehler:
            print(f"  - {f}")
        return 1

    print(f"{args.pfad}: gültig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
