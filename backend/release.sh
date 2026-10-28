#!/usr/bin/env sh
# Paso de despliegue: lo corre el servicio `release` del compose una vez, antes de que arranquen
# web, worker y beat, que esperan a que termine bien. Si algo falla, sale con error y no arranca
# nada con el código nuevo.
set -eu

# lock_timeout: un cambio de esquema que espera detrás de una transacción larga (el pg_dump del
# respaldo, por ejemplo) falla en vez de dejar en cola todas las consultas que llegan detrás.
echo "→ Aplicando migraciones..."
PGOPTIONS="-c lock_timeout=${MIGRATE_LOCK_TIMEOUT:-10s}" python manage.py migrate --noinput

echo "→ Configurando grupos y permisos (admin · editor · autor)..."
python manage.py setup_groups

# En desarrollo no hace falta: runserver sirve los estáticos desde las apps.
if [ "${RELEASE_COLLECTSTATIC:-1}" = "1" ]; then
  echo "→ Recolectando estáticos..."
  python manage.py collectstatic --noinput
fi

echo "✓ release completo"
