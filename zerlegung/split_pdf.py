#!/usr/bin/env python3
"""Teilt eine amtliche Abiturklausur-PDF (Schüler- und Lehrkraft-Seiten gemischt)
in eine Schüler-PDF (Klausur) und eine Lehrkraft-PDF (nur Modelllösungen) auf.

Die amtlichen PDFs von abitur.nrw enthalten nach jedem Aufgabenblock direkt die
"Unterlagen für die Lehrkraft" (Kernlehrplan-Bezüge, Modelllösungen, Bewertungsbogen).
Würde man sie unverändert als Klausur-PDF hochladen, sähen Schüler die Musterlösungen
neben den Aufgaben – ein Verstoß gegen "Erwartungshorizonte sind nur für Lehrkräfte
sichtbar" (CLAUDE.md). Dieses Skript trennt die Seiten anhand von vorher bestimmten
Seitenlisten (keine automatische Erkennung – die Seiten müssen manuell durchgesehen
und zugeordnet werden).

Nutzung:
    python zerlegung/split_pdf.py quelle.pdf \\
        --schueler 1-6,16-18,24-26 \\
        --lehrkraft 8-10,20-21 \\
        --out-praefix M-2026-GK-HT-CAS
"""

import argparse
import sys
from pathlib import Path

import pymupdf as fitz


def parse_seiten(spec: str) -> list[int]:
    seiten = []
    for teil in spec.split(","):
        teil = teil.strip()
        if not teil:
            continue
        if "-" in teil:
            start, ende = teil.split("-")
            seiten.extend(range(int(start), int(ende) + 1))
        else:
            seiten.append(int(teil))
    return seiten


def extrahiere(quelle: Path, seiten: list[int], ziel: Path) -> None:
    quelldoc = fitz.open(quelle)
    neu = fitz.open()
    for seite in seiten:
        neu.insert_pdf(quelldoc, from_page=seite - 1, to_page=seite - 1)
    neu.save(ziel)
    neu.close()
    quelldoc.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("quelle", type=Path)
    parser.add_argument(
        "--schueler", required=True, help="Seiten für die Klausur-PDF, z. B. 1-6,16-18"
    )
    parser.add_argument(
        "--lehrkraft", required=True, help="Seiten für die -ewh.pdf (nur Modelllösungen)"
    )
    parser.add_argument("--out-praefix", required=True, help="z. B. M-2026-GK-HT-CAS")
    parser.add_argument("--out-dir", type=Path, default=Path("zerlegung/pakete/dateien"))
    args = parser.parse_args()

    if not args.quelle.exists():
        print(f"Quelle nicht gefunden: {args.quelle}", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    klausur_ziel = args.out_dir / f"{args.out_praefix}.pdf"
    ewh_ziel = args.out_dir / f"{args.out_praefix}-ewh.pdf"

    extrahiere(args.quelle, parse_seiten(args.schueler), klausur_ziel)
    extrahiere(args.quelle, parse_seiten(args.lehrkraft), ewh_ziel)

    print(f"Geschrieben: {klausur_ziel}")
    print(f"Geschrieben: {ewh_ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
