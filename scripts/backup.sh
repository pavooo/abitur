#!/usr/bin/env sh
# Tägliches Backup von Datenbank und media/-Volume für die Produktionsumgebung.
# Läuft auf dem Server (nicht in einem Container) per Cronjob, z. B.:
#   0 3 * * * cd /pfad/zum/repo && ./scripts/backup.sh >> /var/log/abitur-backup.log 2>&1
#
# Sichert nur lokal (siehe CLAUDE.md/Phase 6: "nur lokal, mit Rotation" –
# kein externer Speicherort). Backups liegen standardmäßig unter ./backups,
# änderbar über BACKUP_VERZEICHNIS. Ältere Backups als BACKUP_AUFBEWAHRUNG_TAGE
# werden automatisch gelöscht.
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DATEI="$REPO_ROOT/docker-compose.prod.yml"
BACKUP_VERZEICHNIS="${BACKUP_VERZEICHNIS:-$REPO_ROOT/backups}"
BACKUP_AUFBEWAHRUNG_TAGE="${BACKUP_AUFBEWAHRUNG_TAGE:-14}"
ZEITSTEMPEL="$(date +%Y-%m-%d_%H-%M-%S)"

# shellcheck disable=SC1090
[ -f "$REPO_ROOT/.env" ] && . "$REPO_ROOT/.env"

mkdir -p "$BACKUP_VERZEICHNIS"

echo "[$ZEITSTEMPEL] Sichere Datenbank..."
docker compose -f "$COMPOSE_DATEI" exec -T db \
  pg_dump -U "${POSTGRES_USER:?POSTGRES_USER fehlt in .env}" "${POSTGRES_DB:?POSTGRES_DB fehlt in .env}" \
  | gzip > "$BACKUP_VERZEICHNIS/db-$ZEITSTEMPEL.sql.gz"

echo "[$ZEITSTEMPEL] Sichere media/-Volume..."
# Fester Name dank `name: abitur` in docker-compose.prod.yml, unabhängig vom
# Verzeichnisnamen beim Klonen.
MEDIA_VOLUME="abitur_media"
docker run --rm \
  -v "$MEDIA_VOLUME":/media-quelle:ro \
  -v "$BACKUP_VERZEICHNIS":/sicherung \
  alpine \
  tar czf "/sicherung/media-$ZEITSTEMPEL.tar.gz" -C /media-quelle .

echo "[$ZEITSTEMPEL] Lösche Backups älter als $BACKUP_AUFBEWAHRUNG_TAGE Tage..."
find "$BACKUP_VERZEICHNIS" -name "db-*.sql.gz" -mtime "+$BACKUP_AUFBEWAHRUNG_TAGE" -delete
find "$BACKUP_VERZEICHNIS" -name "media-*.tar.gz" -mtime "+$BACKUP_AUFBEWAHRUNG_TAGE" -delete

echo "[$ZEITSTEMPEL] Fertig."
