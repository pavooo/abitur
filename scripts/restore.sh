#!/usr/bin/env sh
# Stellt ein mit scripts/backup.sh erstelltes Backup wieder her. ACHTUNG:
# überschreibt die aktuelle Datenbank und den aktuellen media/-Inhalt vollständig.
#
# Nutzung:
#   ./scripts/restore.sh backups/db-2026-01-15_03-00-00.sql.gz backups/media-2026-01-15_03-00-00.tar.gz
set -eu

if [ $# -ne 2 ]; then
  echo "Nutzung: $0 <db-backup.sql.gz> <media-backup.tar.gz>" >&2
  exit 1
fi

DB_BACKUP="$1"
MEDIA_BACKUP="$2"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DATEI="$REPO_ROOT/docker-compose.prod.yml"

# shellcheck disable=SC1090
[ -f "$REPO_ROOT/.env" ] && . "$REPO_ROOT/.env"

printf 'Datenbank "%s" und media/-Volume werden ÜBERSCHRIEBEN. Fortfahren? [y/N] ' "${POSTGRES_DB:-}"
read -r ANTWORT
case "$ANTWORT" in
  y|Y) ;;
  *) echo "Abgebrochen."; exit 1 ;;
esac

echo "Stelle Datenbank wieder her..."
gunzip -c "$DB_BACKUP" | docker compose -f "$COMPOSE_DATEI" exec -T db \
  psql -U "${POSTGRES_USER:?POSTGRES_USER fehlt in .env}" "${POSTGRES_DB:?POSTGRES_DB fehlt in .env}"

echo "Stelle media/-Volume wieder her..."
# Fester Name dank `name: abitur` in docker-compose.prod.yml, unabhängig vom
# Verzeichnisnamen beim Klonen.
MEDIA_VOLUME="abitur_media"
docker run --rm \
  -v "$MEDIA_VOLUME":/media-ziel \
  -v "$(cd "$(dirname "$MEDIA_BACKUP")" && pwd)":/sicherung:ro \
  alpine sh -c "rm -rf /media-ziel/* && tar xzf /sicherung/$(basename "$MEDIA_BACKUP") -C /media-ziel"

echo "Fertig. Dienste ggf. neu starten: docker compose -f docker-compose.prod.yml restart web"
