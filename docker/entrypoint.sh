#!/usr/bin/env sh
set -eu

python app/manage.py migrate --noinput
tailwindcss -i app/static/css/input.css -o app/static/css/tailwind.css

exec "$@"
