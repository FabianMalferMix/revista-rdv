#!/usr/bin/env sh
# Restauración desde un respaldo.  Uso:
#   RESTORE_CONFIRM=SI-DESTRUIR-<base> restore.sh <timestamp|latest>
#
# ⚠️ DESTRUCTIVO: recrea el esquema (pg_restore --clean) y REEMPLAZA los volúmenes de
#    medios. En producción, detén `web` (y worker/beat) antes, para evitar conexiones
#    activas mientras se recrea el esquema.
set -eu

# Confirmación explícita (hallazgo S-06): antes bastaba con invocarlo sin argumentos
# —`latest` era el valor por defecto— para arrasar la base y los medios de producción.
# Se exige nombrar la base que se va a destruir, para que no ocurra por inercia.
ESPERADO="SI-DESTRUIR-${POSTGRES_DB}"
if [ "${RESTORE_CONFIRM:-}" != "$ESPERADO" ]; then
  echo "✗ restore.sh DESTRUYE la base '${POSTGRES_DB}' y los volúmenes de medios."
  echo "  Para confirmar, repite el nombre de la base:"
  echo "      RESTORE_CONFIRM=$ESPERADO  restore.sh ${1:-latest}"
  exit 1
fi

TS="${1:-latest}"
if [ "$TS" = "latest" ]; then
  SRC=$(ls -1dt /backups/*/ 2>/dev/null | head -1)
else
  SRC="/backups/$TS/"
fi
[ -n "${SRC:-}" ] && [ -d "$SRC" ] || { echo "✗ no existe el respaldo: ${SRC:-$TS}"; exit 1; }
echo "→ restaurando desde $SRC"

echo "→ pg_restore (--clean --if-exists)"
PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
  -h "${POSTGRES_HOST:-db}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner --no-acl "$SRC/db.dump"

if [ -f "$SRC/media.tar.gz" ]; then
  echo "→ restaurando media"
  rm -rf /volumes/media/* 2>/dev/null || true
  tar xzf "$SRC/media.tar.gz" -C /volumes/media
fi
if [ -f "$SRC/private_media.tar.gz" ]; then
  echo "→ restaurando private_media"
  rm -rf /volumes/private_media/* 2>/dev/null || true
  tar xzf "$SRC/private_media.tar.gz" -C /volumes/private_media
fi

echo "✓ restauración completa desde $SRC"
