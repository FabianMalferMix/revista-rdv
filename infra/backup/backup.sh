#!/usr/bin/env sh
# Respaldo del archivo: dump de PostgreSQL (formato custom) + tar de media/private_media.
# Se ejecuta dentro de un contenedor con pg_dump y acceso a los volúmenes y a /backups.
# Los respaldos van a /backups, que DEBE ser un almacenamiento que sobreviva a
# `docker compose down -v` y a la pérdida del disco (bind-mount del host / externo).
set -eu

TS=$(date +%Y%m%d-%H%M%S)
DEST="/backups/$TS"
mkdir -p "$DEST"

echo "→ pg_dump de '$POSTGRES_DB'"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "${POSTGRES_HOST:-db}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --format=custom --file="$DEST/db.dump"

echo "→ archivando volúmenes de medios"
tar czf "$DEST/media.tar.gz" -C /volumes/media . 2>/dev/null || echo "  (media vacío)"
tar czf "$DEST/private_media.tar.gz" -C /volumes/private_media . 2>/dev/null || echo "  (private_media vacío)"

# Retención: conservar los últimos BACKUP_KEEP respaldos (rotación diaria simple).
KEEP="${BACKUP_KEEP:-14}"
ls -1dt /backups/*/ 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r old; do
  echo "→ purgando respaldo antiguo: $old"
  rm -rf "$old"
done

echo "✓ respaldo completo en $DEST ($(du -sh "$DEST" 2>/dev/null | cut -f1))"
