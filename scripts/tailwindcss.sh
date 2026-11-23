#!/usr/bin/env sh
# Lädt (einmalig) das passende Tailwind-CLI-Standalone-Binary herunter und führt es aus.
# Kein Node/npm nötig. Nutzung z. B.:
#   scripts/tailwindcss.sh -i app/tailwind/input.css -o app/static/css/tailwind.css --watch
set -eu

TAILWIND_VERSION="4.3.5"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="$REPO_ROOT/.bin"

os="$(uname -s)"
arch="$(uname -m)"

case "$os" in
  Darwin) plattform="macos" ;;
  Linux) plattform="linux" ;;
  *) echo "Nicht unterstütztes Betriebssystem: $os" >&2; exit 1 ;;
esac

case "$arch" in
  arm64|aarch64) architektur="arm64" ;;
  x86_64|amd64) architektur="x64" ;;
  *) echo "Nicht unterstützte Architektur: $arch" >&2; exit 1 ;;
esac

binary_name="tailwindcss-${plattform}-${architektur}"
binary_pfad="$BIN_DIR/${binary_name}-${TAILWIND_VERSION}"

if [ ! -x "$binary_pfad" ]; then
  mkdir -p "$BIN_DIR"
  url="https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/${binary_name}"
  echo "Lade Tailwind-CLI ${TAILWIND_VERSION} (${binary_name}) herunter..." >&2
  curl -sL "$url" -o "$binary_pfad"
  chmod +x "$binary_pfad"
fi

exec "$binary_pfad" "$@"
