#!/usr/bin/env sh
# Restauración desde un respaldo.  Uso: restore.sh <timestamp|latest>
# ⚠️ En producción, detén el servicio `web` (y worker/beat) antes de restaurar,
#    para evitar conexiones activas mientras se recrea el esquema.
set -eu

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
