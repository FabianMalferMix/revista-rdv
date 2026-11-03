#!/usr/bin/env sh
# Paso de despliegue: lo corre el servicio `release` del compose una vez, antes de que arranquen
# web, worker y beat, que esperan a que termine bien. Si algo falla, sale con error y no arranca
# nada con el código nuevo.
set -eu

# lock_timeout: un cambio de esquema que espera detrás de una transacción larga (el pg_dump del
# respaldo, por ejemplo) falla en vez de dejar en cola todas las consultas que llegan detrás.
# statement_timeout=0: una migración de datos puede tardar más que una petición (settings.py
# suma PGOPTIONS a las opciones de la conexión).
echo "→ Aplicando migraciones..."
PGOPTIONS="-c lock_timeout=${MIGRATE_LOCK_TIMEOUT:-10s} -c statement_timeout=0" python manage.py migrate --noinput

echo "→ Configurando grupos y permisos (admin · editor · autor)..."
python manage.py setup_groups

# En desarrollo no hace falta: runserver sirve los estáticos desde las apps. Acepta los mismos
# valores de sí o no que config/env.py, y cualquier otro detiene el despliegue.
case "$(printf '%s' "${RELEASE_COLLECTSTATIC:-1}" | tr '[:upper:]' '[:lower:]')" in
  1 | true | yes | on)
    echo "→ Recolectando estáticos..."
    python manage.py collectstatic --noinput
    ;;
  0 | false | no | off) ;;
  *)
    echo "RELEASE_COLLECTSTATIC=${RELEASE_COLLECTSTATIC} no es un valor de sí o no: usa 1 o 0, true o false, yes o no, on u off." >&2
    exit 1
    ;;
esac

echo "✓ release completo"
