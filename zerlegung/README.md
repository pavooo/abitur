# Zerlegung

Werkzeug für Claude Code, um Abiturklausur-PDFs in strukturierte Aufgaben/Teilaufgaben
zu zerlegen und als Import-Paket für die App vorzubereiten. **Kein Teil der Web-App** –
hier läuft kein Django, keine Datenbank; nur Python-Skripte und JSON-Dateien.

## Ordner

- `eingang/` – echte Klausur-PDFs, die zerlegt werden sollen (git-ignoriert, urheberrechtlich geschützt)
- `taxonomien/<fach>.json` – Themenbaum je Fach (z. B. `mathematik.json`), wird committet
- `quellen/` – Kernlehrpläne und Abitur-Vorgaben zum Abgleich der Taxonomie (git-ignoriert)
- `pakete/` – fertige Import-Pakete (ZIP), bereit zum Hochladen im Adminbereich (git-ignoriert)
- `validate.py` – validiert JSON-Dateien/Pakete gegen `schema/` (siehe unten)

## Arbeitsschritte je Klausur

1. **PDF lesen**: Seiten aus `eingang/` visuell auswerten (Formeln, Graphen, Tabellen –
   nicht nur den reinen Text extrahieren, sondern die Seite wirklich ansehen).
2. **Metadaten bestimmen**: Fach, Jahr, Kursart (`GK`/`LK`), Variante (z. B. A/B, Wahlteil),
   Titel, Hilfsmittel (`TR` für WTR/GTR, oder `CAS`).
3. **Termin bestimmen** (`haupttermin`/`nachschreibtermin`) – steht meist auf dem Deckblatt.
   **Ist das nicht eindeutig erkennbar: nachfragen, nicht raten.** Im Zweifel niemals als
   Haupttermin behandeln (siehe CLAUDE.md, Abschnitt Nachschreibklausuren).
4. **Aufgaben erkennen**: Nummer, Kontext (z. B. „Bakterienwachstum"), Seitenbereich,
   Prüfungsteil (`hilfsmittelfrei`/`mit_hilfsmitteln`), Aufgabenbereich
   (`pflicht`/`wahlpflicht`/`keine_angabe` – bei älteren Klausuren ohne diese Einteilung
   `keine_angabe` verwenden, nicht raten).
5. **Teilaufgaben erkennen**: Bezeichnung (z. B. `2b`), Seite, Text **sinngetreu** übernehmen
   (Formeln als LaTeX, z. B. `$f'(x) = 3x^2 - 2x$`), Punkte (falls angegeben).
6. **Themen zuordnen**: ausschließlich Kennungen aus `taxonomien/<fach>.json` verwenden –
   niemals neue Kennungen erfinden. Auch implizit verwendete Themen erkennen (z. B. wenn eine
   Teilaufgabe Symmetrie nutzt, ohne das Wort zu erwähnen). Fehlt ein passendes Thema wirklich,
   dem Nutzer melden statt die Taxonomie eigenmächtig zu erweitern.
7. **Anforderungsbereich** (`I`/`II`/`III`), **Operatoren** (die tatsächlich verwendeten
   Operatoren, z. B. `ermitteln`, `begründen`) und eine **kurze Begründung** der
   Themenzuordnung je Teilaufgabe festhalten.
8. **Gegen Schema validieren**: `python zerlegung/validate.py zerlegung/pakete/<name>.zip`
   (oder einzelne JSON-Dateien vorab). Erst bei `gültig.` weitermachen.
9. **Als ZIP ablegen** unter `zerlegung/pakete/zerlegung-<fach>-<datum>.zip` (Format s. u.).

## Paketformat

```
zerlegung-<fach>-<datum>.zip
├── manifest.json            # schema_version, fach, erstellt_am
├── taxonomie.json           # optional: neue/aktualisierte Themen (siehe unten)
├── klausuren/
│   └── <klausur-id>.json
└── dateien/
    ├── <klausur-id>.pdf
    └── <klausur-id>-ewh.pdf # Erwartungshorizont, optional
```

`<klausur-id>` ist frei wählbar, muss aber mit dem Dateinamen in `dateien/` übereinstimmen,
z. B. `M-2024-LK-HT-A`. Genaue Feldformate stehen in `schema/*.schema.json`.

## Taxonomie (`taxonomien/<fach>.json`)

Flache Liste; jedes Thema verweist per `eltern` auf die Kennung seines Elternthemas
(`null` bei einem Wurzelthema). Felder je Thema: `kennung` (stabil, vollständiger Pfad wie
`analysis.diff.wendepunkt`), `name`, `eltern`, `kursniveau` (`alle`/`LK`), `synonyme`.

Ein Entwurf für Mathematik liegt vor. **Solange `status` darin `"entwurf"` ist oder einzelne
Themen noch `zu_pruefen` tragen, lehnt die App den Import ab** – das ist beabsichtigt
("nur fertige, geprüfte Daten"). Beim Abgleich gegen die Kernlehrpläne in `quellen/`:
Kursniveau je Thema korrigieren, fehlende Themen ergänzen, **Abweichungen als Liste zur
Bestätigung vorlegen, nicht still ändern** – erst nach Bestätigung `zu_pruefen`/`status`
entfernen.

Ein Taxonomie-Update kann zusammen mit Klausuren im selben Paket geliefert werden, oder
eigenständig (Paket ohne `klausuren/`), wenn nur die Taxonomie aktualisiert werden soll.

## Validierung

`validate.py` prüft nur die JSON-Struktur gegen `schema/` – dieselben Schemata, die auch
die App beim Import nutzt. Fachliche Prüfungen (existiert das Fach? ist die Themen-Kennung
schon bekannt?) macht erst der Import in der App, weil sie die Datenbank braucht.

```bash
python zerlegung/validate.py zerlegung/taxonomien/mathematik.json
python zerlegung/validate.py zerlegung/pakete/zerlegung-m-2026-01-15.zip
```
