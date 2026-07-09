#!/usr/bin/env bash
set -e

echo "→ Aplicando migraciones..."
python manage.py migrate --noinput

echo "→ Configurando grupos y permisos (admin · editor · autor)..."
python manage.py setup_groups

if [ "${DJANGO_COLLECTSTATIC:-0}" = "1" ]; then
  echo "→ Recolectando estáticos..."
  python manage.py collectstatic --noinput
fi

exec "$@"
