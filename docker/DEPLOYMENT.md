# Produktions-Deployment (Hetzner)

Läuft als eigenes Docker-Compose-Projekt neben dem bereits vorhandenen
[Nginx Proxy Manager](https://nginxproxymanager.com/) (NPM, Container
`nginx-proxy-manager`, Compose-Projekt "webprojekt", Netzwerk
"webprojekt_default" – eigenes, separates Compose-Projekt, nicht Teil dieses
Repos). NPM verwaltet Domains/TLS-Zertifikate über seine Weboberfläche, nicht
über von Hand bearbeitete nginx-Dateien.

## Einmalige Einrichtung

1. Repo auf den Server klonen, `.env.example` nach `.env` kopieren und befüllen:
   - `DJANGO_SECRET_KEY`: zufälliger Wert (`openssl rand -hex 32`)
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS`: die echte Domain (z. B. `abitur.beispiel-domain.de`)
   - `DJANGO_CSRF_TRUSTED_ORIGINS`: `https://` + dieselbe Domain
   - `DJANGO_ADMIN_PFAD`: zufälliger, nicht erratbarer Pfad
   - `POSTGRES_PASSWORD`: starkes Passwort (nicht den Dev-Standardwert übernehmen)
2. Starten: `docker compose -f docker-compose.prod.yml up -d --build`
   (der `web`-Service hängt automatisch auch im Netzwerk `webprojekt_default`,
   somit für NPM unter dem Namen `web` erreichbar – kein zusätzlicher Schritt
   nötig, da der Netzwerkname in `docker-compose.prod.yml` bereits eingetragen ist).
3. Media-Volume (`abitur_media`) read-only im Compose-Projekt "webprojekt"
   (dort, wo NPM selbst definiert ist) einbinden, dann dieses Projekt neu
   starten. Details und der Custom-Nginx-Konfiguration-Block für die
   geschützte Dateiauslieferung stehen in
   `docker/nginx/abitur-npm-custom-location.conf.beispiel`.
4. In der NPM-Weboberfläche einen neuen Proxy Host anlegen: Domain eintragen,
   Forward Hostname/IP `web`, Forward Port `8000`, SSL wie bei den anderen
   Proxy Hosts (Let's Encrypt o. ä.). Im Tab "Advanced" den Block aus
   `docker/nginx/abitur-npm-custom-location.conf.beispiel` einfügen.
5. Ersten Admin-Account anlegen: Registrierung über `/lehrkraft/registrieren/`
   auf der laufenden Seite – die erste Registrierung wird automatisch Admin
   (siehe `accounts/forms.py`).
6. Backup-Cronjob einrichten (siehe unten).

## Updates ausrollen

```sh
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

`entrypoint.sh` führt bei jedem Start automatisch `migrate`, den Tailwind-Build
und `collectstatic` aus.

## Backups

`scripts/backup.sh` sichert Datenbank (`pg_dump`) und das `media`-Volume lokal
nach `./backups` (änderbar über `BACKUP_VERZEICHNIS`) und löscht automatisch
Backups älter als 14 Tage (änderbar über `BACKUP_AUFBEWAHRUNG_TAGE`). Bewusst
nur lokal auf dem Server, kein externer Speicherort (siehe CLAUDE.md, Phase 6).

Cronjob einrichten:

```cron
0 3 * * * cd /pfad/zum/repo && ./scripts/backup.sh >> /var/log/abitur-backup.log 2>&1
```

Wiederherstellen: `scripts/restore.sh <db-backup.sql.gz> <media-backup.tar.gz>`
(überschreibt die aktuelle Datenbank und den aktuellen media-Inhalt vollständig
– vorher unbedingt ein frisches Backup der aktuellen Daten ziehen, falls diese
noch gebraucht werden könnten).

## Was dieses Repo nicht verwaltet

- TLS-Zertifikate (verwaltet Nginx Proxy Manager bereits für andere Seiten).
- Das "webprojekt"-Compose-Projekt (NPM) selbst und dessen Netzwerk/Volumes.
- Monitoring/Alerting.
