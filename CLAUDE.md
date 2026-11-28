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
- PDF: PyMuPDF für Seitenvorschaubilder beim Import sowie für PDF-Prüfung/Textextraktion/
  Bereichsmarkierung im Lehrkraft-Editor
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
  editor/            # Lehrkraft-Editor: Upload, Zerlegung, Status-Workflow
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
- Klausuren aus dem Lehrkraft-Editor zur Freigabe prüfen, freigeben oder mit Kommentar ablehnen
  (siehe Abschnitt „Lehrkraft-Editor“)
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
  Mit dem Lehrkraft-Editor kommt der Freigabe-`status` als zweite Sichtbarkeitsdimension hinzu
  (siehe Abschnitt „Lehrkraft-Editor“); er wird ebenfalls ausschließlich hier geprüft, nicht in
  einzelnen Views.
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
  (z. B. `analysis.diff.wendepunkt`), Name, Synonymliste, Kursniveau (`alle`|`LK`)
- **Klausur**: Fach, Jahr, Kursart (`GK`|`LK`), Termin, Variante (z. B. A/B, Wahlteil),
  Titel, Hilfsmittel (`TR`: Taschenrechner, umfasst WTR/GTR|`CAS`), PDF, Erwartungshorizont-PDF (optional),
  Importprotokoll-Referenz, Status (`entwurf`|`eingereicht`|`freigegeben`|`abgelehnt`,
  siehe Abschnitt „Lehrkraft-Editor“), Ersteller (Lehrkraft, leer bei Admin-Import),
  Ablehnungskommentar (Pflicht bei Status `abgelehnt`)
  Eindeutig: Fach + Jahr + Kursart + Termin + Variante
- **Aufgabe**: Klausur, Nummer, Titel/Kontext (z. B. „Bakterienwachstum“), Seitenbereich,
  Prüfungsteil (`hilfsmittelfrei`|`mit_hilfsmitteln`), Aufgabenbereich
  (`pflicht`|`wahlpflicht`|`keine_angabe`, für ältere Klausuren ohne diese Einteilung)
- **Teilaufgabe**: Aufgabe, Bezeichnung (z. B. `2b`), Text, Seite, Punkte (optional),
  Themen (M2M), Anforderungsbereich (I–III), Operatoren, Begründung der Zuordnung
- **Bereich**: gehört zu genau einer Aufgabe oder einer Teilaufgabe, Seite, Koordinaten
  normiert auf 0–1 relativ zur Seitengröße. Mehrere Bereiche pro Aufgabe/Teilaufgabe möglich,
  auch über mehrere Seiten. Entsteht nur im Lehrkraft-Editor (siehe dort), nicht beim Admin-Import.
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
  "hilfsmittel": "TR",
  "aufgaben": [
    {
      "nummer": 1,
      "kontext": "Bakterienwachstum",
      "seiten": [2, 3],
      "pruefungsteil": "mit_hilfsmitteln",
      "aufgabenbereich": "pflicht",
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
- Nur Admins dürfen importieren. Dieser Weg bleibt unverändert neben dem Lehrkraft-Editor
  bestehen; importierte Klausuren erhalten direkt Status `freigegeben`.
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
  - Prüfungsteil (hilfsmittelfrei / mit Hilfsmitteln), Aufgabenbereich und Hilfsmittel
    aus dem Dokument bestimmen
- `taxonomien/mathematik.json`: Themenbaum Mathematik (Analysis, Analytische Geometrie und
  Lineare Algebra, Stochastik). Ein Entwurf liegt vor; in Phase 4 prüft Claude ihn gegen die
  Kernlehrpläne (2014 und 2023) und die Abitur-Vorgaben in `zerlegung/quellen/`:
  Kursniveau (GK/LK) je Thema korrigieren, fehlende Themen ergänzen, Abweichungen
  als Liste zur Bestätigung vorlegen, nicht still ändern.
- `eingang/`, `pakete/`, `quellen/`: in `.gitignore`
- Validierungsskript `zerlegung/validate.py`, das dieselben Schemata nutzt wie die App

## Suche
- Kombiniert Volltext, Themen (inkl. Unterthemen) und Synonyme.
- Filter: Fach (wenn mehrere), Jahr, Kursart, Thema, Anforderungsbereich, Hilfsmittel und
  Prüfungsteil. Der Filter „nur hilfsmittelfrei“ ist für SuS prominent sichtbar.
  Termin-Filter nur für Lehrkräfte im aktivierten Nachschreibmodus.
- Treffer auf Ebene der Teilaufgabe, gruppiert nach Klausur, mit Link zur passenden PDF-Seite.
- Themenbrowser: Themenbaum durchklicken → alle passenden Teilaufgaben.

## Lehrkraft-Editor
Zusätzlich zum Admin-Import (siehe oben) können Lehrkräfte Klausuren selbst hochladen und in
einem geführten Editor zerlegen. Weiterhin gilt uneingeschränkt: **keine KI-Aufrufe zur
Laufzeit.** Unterstützung erfolgt nur durch regelbasierte Vorschläge und optional durch JSON,
das die Lehrkraft mit einem eigenen, externen KI-Werkzeug erzeugt (Option C unten) – die App
selbst ruft dabei nichts auf.

### Status-Workflow (Freigabe durch Admin)
- `status`: `entwurf` → `eingereicht` → `freigegeben`, oder `eingereicht` → `abgelehnt`
  (mit Pflichtkommentar des Admins) → zurück in Bearbeitung durch die Lehrkraft.
- Nur `freigegeben` ist für SuS und andere Lehrkräfte sichtbar. Entwürfe, eingereichte und
  abgelehnte Klausuren sehen nur die erstellende Lehrkraft und Admins.
- Der Status wird ausschließlich in `sichtbar_fuer` berücksichtigt (siehe Abschnitt
  „Nachschreibklausuren“), nie in einzelnen Views.
- Migration: bereits vorhandene Klausuren erhalten `freigegeben`. Admin-Importe setzen
  weiterhin direkt `freigegeben`.
- Freigegebene Klausuren dürfen nur noch Admins bearbeiten.
- Adminbereich: Liste „Zur Freigabe“, Detailansicht mit PDF, eingezeichneten Bereichen und
  allen Daten; der Termin (Haupt-/Nachschreibtermin) ist dort deutlich hervorgehoben, damit
  eine falsche Angabe vor der Freigabe auffällt. Aktionen: Freigeben / Ablehnen mit Kommentar.
- Lehrkräfte sehen unter „Meine Klausuren“ den Status und ggf. den Ablehnungskommentar.

### Editor (Assistent in 4 Schritten, Zwischenstand wird automatisch gespeichert)
1. **Metadaten**: Fach (nur zugeordnete Fächer), Jahr, Kursart GK/LK, Variante, Hilfsmittel,
   Titel. Termin ist Pflicht und hat **keinen** Standardwert. Existiert der eindeutige
   Schlüssel bereits, wird gewarnt.
2. **PDF & Aufgaben**: Upload des Klausur-PDFs (optional Erwartungshorizont). Seiten werden
   angezeigt; die Lehrkraft legt Aufgaben an (Nummer, Kontext, Prüfungsteil, Aufgabenbereich)
   und markiert deren Bereiche per Rechteck auf den Seiten.
3. **Teilaufgaben**: Je Teilaufgabe Bereich(e) per Rechteck markieren. Der Text wird aus dem
   markierten Bereich vorbefüllt und ist bearbeitbar. Dazu Punkte, Operatoren,
   Anforderungsbereich und Themen, jeweils mit Vorschlägen (siehe unten).
4. **Prüfen & Einreichen**: Zusammenfassung mit Hinweisen auf Lücken (z. B. Teilaufgabe ohne
   Thema, Aufgabe ohne Bereich). Einreichen nur, wenn Pflichtangaben vollständig sind.

### Bereichsmarkierung
- PDF-Anzeige im Browser mit PDF.js, lokal ausgeliefert (kein CDN). Das PDF kommt über die
  bestehende geschützte Auslieferungs-View.
- Rechtecke ziehen, verschieben, in der Größe ändern und löschen. Eine Aufgabe/Teilaufgabe kann
  mehrere Bereiche haben, auch über mehrere Seiten (Modell `Bereich`, siehe „Datenmodell“).
- Textextraktion serverseitig mit PyMuPDF (`get_text(clip=...)`). Bei Seiten ohne Textebene
  vorher OCRmyPDF (lokal auf dem Server).
- JavaScript so schlank wie möglich: Vanilla JS oder Alpine.js, kein Build-Framework. Die
  Kommunikation mit dem Server läuft über HTMX bzw. normale Formular-Posts mit CSRF.
- Optional, wenn wenig Aufwand: in Suchtreffern einen Bildausschnitt der Teilaufgabe zeigen.

### Regelbasierte Vorschläge (eigenes Modul, reine Funktionen, gut getestet)
- **Teilaufgaben:** Muster wie „a)“, „1.2“, „(6 Punkte)“ erkennen und eine Aufteilung vorschlagen.
- **Operatoren:** Abgleich mit einer Operatorenliste je Fach (z. B.
  `schema/operatoren/mathematik.json` mit Operator → typischer Anforderungsbereich; liegt
  unter `schema/`, nicht unter `zerlegung/`, da die Liste zur Laufzeit von der App selbst
  gelesen wird – analog zu den JSON-Schemata, die ebenfalls von App und `zerlegung/`
  gemeinsam genutzt werden). Daraus den Anforderungsbereich vorschlagen.
- **Themen:** Abgleich des Textes mit Themennamen und Synonymen der Taxonomie
  (Kleinschreibung, Umlaute normalisieren, einfache Wortstamm-Toleranz). Treffer nach
  Relevanz sortieren.
- Vorschläge werden als anklickbare Chips angezeigt und **nie** ungefragt übernommen.
- Zusätzlich manuelle Themenauswahl: Baumansicht + Suchfeld über Namen und Synonyme.

### Option C: JSON aus eigenem KI-Werkzeug
- In Schritt 3 Button „Prompt für eigenes KI-Werkzeug erzeugen“. Der erzeugte Prompt enthält:
  die Metadaten aus Schritt 1, die Taxonomie des Fachs (Kennung, Name, Synonyme), das exakte
  erwartete JSON-Format mit einem vollständigen Beispiel und die Anweisung, ausschließlich
  gültiges JSON auszugeben. Mit Kopier-Button und Download als `.txt`.
- Feld „JSON einfügen“. Validierung mit **demselben** Schema wie der Import (nur der
  Aufgabenteil). Die Metadaten aus Schritt 1 haben Vorrang; Abweichungen im JSON, insbesondere
  beim Termin, werden angezeigt und müssen bestätigt werden.
- Fehlermeldungen auf Deutsch mit genauem Pfad, z. B. „Aufgabe 2, Teilaufgabe b: Thema
  `analysis.diff.wendepunkt.xyz` existiert nicht“.
- Die UI muss klar zeigen, welches Format erwartet wird: Kurzbeschreibung direkt am Feld,
  aufklappbares Beispiel-JSON und ein Link zur vollständigen Formatbeschreibung.
- Das JSON enthält keine Koordinaten, sondern nur Seitenzahlen. Fehlende Bereiche werden in
  Schritt 4 als Lücke angezeigt und von der Lehrkraft nachgezeichnet.
- Hinweis in der UI: Die App sendet nichts an KI-Dienste. Die Lehrkraft entscheidet selbst, ob
  sie das PDF in ein eigenes Werkzeug lädt.

### Sicherheit (zusätzlich zu „Authentifizierung & Sicherheit“)
- Upload nur für Lehrkräfte und nur in zugeordneten Fächern.
- Nur PDF: Prüfung von Dateiendung, MIME-Typ und Magic Bytes sowie Öffnen-Test mit PyMuPDF.
  Größenlimit (z. B. 30 MB) und Seitenlimit konfigurierbar über Umgebungsvariablen.
- Speicherung außerhalb des Webroots unter zufälligem Dateinamen.
- **Pflicht-Tests** (zusätzlich zu den bestehenden Nachschreib-Tests):
  - SuS sehen niemals Klausuren mit Status ≠ `freigegeben` (Suche, Detail, Download,
    Vorschaubilder, Zählungen).
  - Lehrkraft B sieht keine Entwürfe von Lehrkraft A.
  - Lehrkräfte können Klausuren nur in ihren zugeordneten Fächern hochladen/bearbeiten, und
    nach Freigabe nicht mehr selbst bearbeiten.

## Nicht-Ziele (vorerst)
- Keine KI-Aufrufe zur Laufzeit der App – auch Option C im Lehrkraft-Editor ruft kein
  KI-Modell von der App aus auf, sondern erzeugt nur einen Prompt für ein externes,
  eigenes Werkzeug der Lehrkraft.
- Keine personalisierten SuS-Konten, keine Lösungsabgabe
- Keine öffentliche API, keine Native-App

---

## Phasen
1. Projektgerüst, Docker Compose (dev), Rollen, Login (Lehrkraft + Code), Adminbereich
   (Lehrkräfte, Fächer, Codes)
2. Datenmodell + zentrale Sichtbarkeitslogik inkl. Pflicht-Tests für Nachschreibklausuren
3. JSON-Schemata + Import (Validierung, Vorschau, Transaktion, Protokoll, Management-Command)
4. `zerlegung/`: README, Mathematik-Taxonomie prüfen (gegen Lehrpläne in `quellen/`),
   Validierungsskript; erster Testimport mit 2–3 echten Klausuren
5. Suche, Themenbrowser, Klausuransicht, Nachschreibmodus für Lehrkräfte
6. Produktions-Deployment auf Hetzner (Compose prod, nginx-Snippet mit `X-Accel-Redirect`, Backups)
7. Lehrkraft-Editor (siehe Abschnitt „Lehrkraft-Editor“), in Teilphasen E1–E5:
   - E1: Status-Workflow (Datenmodell, zentrale Sichtbarkeit, Admin-Freigabeliste,
     „Meine Klausuren“, Pflicht-Tests)
   - E2: Upload + Editor-Grundgerüst (Schritt 1, PDF-Sicherheitsprüfungen, Autosave)
   - E3: PDF-Anzeige & Bereichsmarkierung (PDF.js, Modell `Bereich`, Schritt 2, Textextraktion)
   - E4: Teilaufgaben-Schritt & regelbasierte Vorschläge (Schritt 3, Operatoren, Themen-Abgleich)
   - E5: Prüfen & Einreichen, Option C (Schritt 4, Prompt-Generator, JSON-Einfügen & -Validierung)

Arbeite immer nur an der aktuellen Phase (bzw. Teilphase). Vor Beginn einer Phase kurz den
Plan nennen und Rückfragen stellen, wenn Anforderungen unklar sind.