#!/usr/bin/env bash
set -e

# Producción corre las migraciones y los grupos como paso de despliegue explícito
# (DJANGO_SKIP_MIGRATE=1), no en cada arranque de web/worker/beat.
if [ "${DJANGO_SKIP_MIGRATE:-0}" != "1" ]; then
  echo "→ Aplicando migraciones..."
  python manage.py migrate --noinput
  echo "→ Configurando grupos y permisos (admin · editor · autor)..."
  python manage.py setup_groups
fi

if [ "${DJANGO_COLLECTSTATIC:-0}" = "1" ]; then
  echo "→ Recolectando estáticos..."
  python manage.py collectstatic --noinput
fi

exec "$@"
