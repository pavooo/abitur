#!/usr/bin/env sh
set -eu

python app/manage.py migrate --noinput
tailwindcss -i app/tailwind/input.css -o app/static/css/tailwind.css
python app/manage.py collectstatic --noinput

exec "$@"
