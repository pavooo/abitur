# Abiturklausuren-Archiv

Web-App zum Einsehen und Durchsuchen alter Abiturklausuren eines NRW-Gymnasiums.
Die Klausuren werden **offline** (mit Claude Code, Ordner `zerlegung/`) in Aufgaben und
Teilaufgaben zerlegt und kategorisiert und anschließend als statisches Import-Paket in die
App übernommen. Zunächst nur Mathematik; die Architektur muss weitere Fächer **ohne
Codeänderung** unterstützen (neues Fach = Anlegen im Adminbereich + Import).

---

## Tech-Stack
- Python 3.12, Django 5.x, PostgreSQL 16
- Abhängigkeiten: `uv` (pyproject.toml + uv.lock)
- Frontend: Django-Templates + HTMX + Tailwind CSS. Kein SPA, keine öffentliche JSON-API.
- Suche: PostgreSQL-Volltextsuche (Konfiguration `german`) + `pg_trgm` für unscharfe Suche
- PDF: PyMuPDF nur für Seitenvorschaubilder beim Import
- Rate-Limiting: django-axes
- **KEINE KI-Aufrufe zur Laufzeit.** Die App enthält keinen Anthropic-API-Schlüssel und
  keine Abhängigkeit zu einem KI-Dienst.
- Deployment: Docker Compose (`web`, `db`) hinter bestehendem nginx-Reverse-Proxy (Hetzner).
  Gunicorn als App-Server, statische Dateien über WhiteNoise.

## Konventionen
- Code, Bezeichner, Commits: Englisch. UI-Texte und Fachbegriffe: Deutsch.
  Domänenbegriffe ohne gute Übersetzung dürfen deutsch bleiben (z. B. `Klausur`, `Erwartungshorizont`).
- Formatierung/Linting: ruff. Tests: pytest + pytest-django.
- Konfiguration und Geheimnisse ausschließlich über Umgebungsvariablen (`.env`, nie committen;
  `.env.example` pflegen).
- Jede View braucht eine explizite Rechteprüfung. Standard ist „verweigern“.
- Kleine, nachvollziehbare Schritte; nach jeder Phase müssen alle Tests grün sein.
- **Klausur-PDFs und Import-Pakete werden niemals committet** (urheberrechtlich geschützt).
  `.gitignore` entsprechend pflegen; Testdaten nur als selbst erstellte Dummy-PDFs.

## Projektstruktur (Ziel)
```
app/                 # Django-Projekt
  config/            # settings, urls, wsgi
  accounts/          # Lehrkräfte, Zugangscodes, Rollen, Login
  archiv/            # Fach, Klausur, Aufgabe, Teilaufgabe, Thema, Sichtbarkeit, Suche
  importer/          # Import-Pakete: Validierung, Vorschau, Import, Protokoll
  adminbereich/      # eigene Admin-Oberfläche
  templates/, static/
zerlegung/           # Werkzeug für Claude Code, NICHT Teil der Web-App
schema/              # JSON-Schemata (von App UND zerlegung/ genutzt)
docker/, docker-compose.yml, .env.example
```

---

## Rollen
- **SuS**: Login nur per Zugangscode (kein Konto, keine E-Mail). Die Session ist an den Code
  gebunden; wird der Code gesperrt oder läuft er ab, endet die Session beim nächsten Request.
- **Lehrkraft**: persönliches Konto (E-Mail + Passwort). Registrierung → Status „ausstehend“
  → Freischaltung durch Admin.
- **Admin**: Lehrkraft mit Admin-Recht.

## Adminbereich (eigene Oberfläche, nicht das Django-Admin)
- Lehrkräfte freischalten, sperren, Fächer zuordnen, Admin-Recht vergeben
- Zugangscodes verwalten: je Code ein Fach + Bezeichnung (z. B. „Mathe-LK Abi 2027“),
  Ablaufdatum, sperrbar. Der Code wird nur einmal bei Erstellung im Klartext angezeigt.
- Fächer anlegen
- Import-Pakete hochladen, prüfen, importieren; Import-Protokoll einsehen
- Zugriffsprotokoll für Nachschreibklausuren einsehen
- Das Django-Admin bleibt nur für Notfälle/Superuser, unter nicht erratbarem Pfad, nicht verlinkt.

## Fächer & Sichtbarkeit
- `Fach` ist ein eigenes Datenmodell; der Themenbaum hängt am Fach.
- Lehrkräfte sehen nur Klausuren ihrer zugeordneten Fächer.
- SuS sehen nur Klausuren des Fachs, für das ihr Code gilt.
- Erwartungshorizonte sind nur für Lehrkräfte sichtbar.

## Nachschreibklausuren — SICHERHEITSKRITISCH
- Jede Klausur hat das Pflichtfeld `termin` (`haupttermin` | `nachschreibtermin`).
- Sichtbarkeit wird an **EINER** zentralen Stelle geregelt:
  `Klausur.objects.sichtbar_fuer(request)` (bzw. analog für Aufgaben/Teilaufgaben).
  Alle Views, Suche, Downloads, Vorschaubilder und Zählungen nutzen ausschließlich diese Methode.
- SuS erhalten Nachschreibklausuren **unter keinen Umständen**: nicht in Treffern,
  Trefferanzahlen, Filteroptionen, Vorschaubildern, Downloads oder Fehlermeldungen.
  Ein direkter Aufruf einer Nachschreib-URL liefert für SuS 404 (nicht 403).
- Dateien (PDFs, Vorschaubilder) liegen außerhalb des Webroots; Auslieferung nur über eine
  View mit Rechteprüfung per nginx `X-Accel-Redirect`.
- Lehrkräfte: Nachschreibklausuren standardmäßig ausgeblendet. Einblenden nur per Schalter
  „Nachschreibklausuren anzeigen“, gültig für die laufende Session. Im aktiven Modus:
  dauerhaftes rotes Banner, roter Rahmen und Markierung an jedem betroffenen Treffer.
- Jeder Abruf einer Nachschreibklausur wird protokolliert (Lehrkraft, Zeitpunkt, Klausur).
- **Pflicht-Tests:** Für jede Route, die Klausurdaten ausgibt, existiert ein Test, der sicherstellt,
  dass ein SuS-Login keine Nachschreibklausur sieht. Neue Routen ohne diesen Test sind unfertig.

## Authentifizierung & Sicherheit
- Passwörter und Zugangscodes nur gehasht speichern.
- Rate-Limiting bei Lehrkraft-Login und Code-Eingabe (django-axes).
- Sichere Cookies, `SECURE_PROXY_SSL_HEADER`, HTTPS-only, HSTS. CSRF überall aktiv.
- Keine personenbezogenen Daten von SuS.

---

## Datenmodell (Kern)
- **Fach**: Name, Kürzel (z. B. `M`)
- **Thema**: gehört zu Fach, hierarchisch (Eltern-Thema), stabile `kennung`
  (z. B. `analysis.diff.wendepunkt`), Name, Synonymliste
- **Klausur**: Fach, Jahr, Kursart (`GK`|`LK`), Termin, Variante (z. B. A/B, Wahlteil),
  Titel, PDF, Erwartungshorizont-PDF (optional), Importprotokoll-Referenz
  Eindeutig: Fach + Jahr + Kursart + Termin + Variante
- **Aufgabe**: Klausur, Nummer, Titel/Kontext (z. B. „Bakterienwachstum“), Seitenbereich
- **Teilaufgabe**: Aufgabe, Bezeichnung (z. B. `2b`), Text, Seite, Punkte (optional),
  Themen (M2M), Anforderungsbereich (I–III), Operatoren, Begründung der Zuordnung
- Volltext-Suchvektor auf Teilaufgabe (Text + Aufgabenkontext + Themennamen + Synonyme)

## Inhalte: Offline-Zerlegung + Import
Zerlegung und Kategorisierung passieren **außerhalb** der App (siehe `zerlegung/README.md`).
Die App importiert nur fertige, geprüfte Daten.

### Import-Paket (ZIP)
```
zerlegung-<fach>-<datum>.zip
├── manifest.json            # Schema-Version, Fach-Kürzel, Erstellungsdatum
├── taxonomie.json           # optional: Themenbaum des Fachs (neu oder aktualisiert)
├── klausuren/
│   └── <klausur-id>.json    # Metadaten, Aufgaben, Teilaufgaben, Themen
└── dateien/
    ├── <klausur-id>.pdf
    └── <klausur-id>-ewh.pdf # Erwartungshorizont (optional)
```

Beispiel `klausuren/<klausur-id>.json` (verkürzt):
```json
{
  "id": "M-2024-LK-HT-A",
  "fach": "M",
  "jahr": 2024,
  "kursart": "LK",
  "termin": "haupttermin",
  "variante": "A",
  "titel": "Analysis – Prüfungsteil B",
  "aufgaben": [
    {
      "nummer": 1,
      "kontext": "Bakterienwachstum",
      "seiten": [2, 3],
      "teilaufgaben": [
        {
          "bezeichnung": "1c",
          "seite": 3,
          "text": "Ermitteln Sie den Zeitpunkt, zu dem der Bestand am stärksten zunimmt.",
          "punkte": 6,
          "themen": ["analysis.diff.wendepunkt", "analysis.anwendung.wachstum"],
          "anforderungsbereich": "II",
          "operatoren": ["ermitteln"],
          "begruendung": "Stärkste Zunahme = Maximum der 1. Ableitung = Wendestelle."
        }
      ]
    }
  ]
}
```

### Import-Regeln
- Nur Admins dürfen importieren.
- Ablauf: Upload → Validierung gegen JSON-Schema (`schema/`) → Vorschau
  (neu / aktualisiert / Fehler je Klausur) → Bestätigung → Import in **einer**
  Datenbanktransaktion (alles oder nichts) → Vorschaubilder erzeugen.
- Erneuter Import mit gleichem eindeutigem Schlüssel aktualisiert die Klausur (inkl. Ersetzen
  ihrer Aufgaben), statt sie zu duplizieren.
- Themen werden über `kennung` referenziert. Unbekannte Kennungen sind ein Fehler,
  sie werden nicht still angelegt.
- `termin` ist Pflicht. Fehlt er oder ist er ungültig, wird die Klausur abgelehnt.
  Im Zweifel nie als Haupttermin behandeln.
- Jeder Import wird protokolliert (wer, wann, Paketname, Ergebnis, Anzahl neu/aktualisiert).
- Zusätzlich Management-Command `import_paket <zip>` für den Erstbestand (gleiche Logik).

## Ordner `zerlegung/` (Werkzeug für Claude Code, nicht Teil der Web-App)
- `README.md`: Arbeitsanweisung für Claude Code:
  - PDFs aus `zerlegung/eingang/` lesen, Seiten visuell auswerten (Formeln, Graphen, Tabellen)
  - Aufgaben/Teilaufgaben erkennen, Text sinngetreu übernehmen (Formeln als LaTeX)
  - Themen **nur** aus `taxonomien/<fach>.json` wählen; implizite Themen erkennen
  - Anforderungsbereich, Operatoren und kurze Begründung je Teilaufgabe
  - Termin (Haupt/Nachschreib) aus dem Dokument bestimmen; wenn unklar: nachfragen
  - Ergebnis gegen `schema/` validieren und als ZIP in `zerlegung/pakete/` ablegen
- `taxonomien/mathematik.json`: Themenbaum Mathematik, angelehnt an den Kernlehrplan NRW
  (Analysis, Lineare Algebra/Analytische Geometrie, Stochastik)
- `eingang/`, `pakete/`: in `.gitignore`
- Validierungsskript `zerlegung/validate.py`, das dieselben Schemata nutzt wie die App

## Suche
- Kombiniert Volltext, Themen (inkl. Unterthemen) und Synonyme.
- Filter: Fach (wenn mehrere), Jahr, Kursart, Thema, Anforderungsbereich.
  Termin-Filter nur für Lehrkräfte im aktivierten Nachschreibmodus.
- Treffer auf Ebene der Teilaufgabe, gruppiert nach Klausur, mit Link zur passenden PDF-Seite.
- Themenbrowser: Themenbaum durchklicken → alle passenden Teilaufgaben.

## Nicht-Ziele (vorerst)
- Keine KI zur Laufzeit
- Keine personalisierten SuS-Konten, keine Lösungsabgabe
- Keine öffentliche API, keine Native-App

---

## Phasen
1. Projektgerüst, Docker Compose (dev), Rollen, Login (Lehrkraft + Code), Adminbereich
   (Lehrkräfte, Fächer, Codes)
2. Datenmodell + zentrale Sichtbarkeitslogik inkl. Pflicht-Tests für Nachschreibklausuren
3. JSON-Schemata + Import (Validierung, Vorschau, Transaktion, Protokoll, Management-Command)
4. `zerlegung/`: README, Mathematik-Taxonomie, Validierungsskript; erster Testimport mit
   2–3 echten Klausuren
5. Suche, Themenbrowser, Klausuransicht, Nachschreibmodus für Lehrkräfte
6. Produktions-Deployment auf Hetzner (Compose prod, nginx-Snippet mit `X-Accel-Redirect`, Backups)

Arbeite immer nur an der aktuellen Phase. Vor Beginn einer Phase kurz den Plan nennen und
Rückfragen stellen, wenn Anforderungen unklar sind.
