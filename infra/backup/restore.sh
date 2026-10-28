#!/usr/bin/env sh
# Restauración desde un respaldo.  Uso:
#   RESTORE_CONFIRM=SI-DESTRUIR-<base> restore.sh [--db-only|--media-only] <fecha|latest>
#   RESTORE_CONFIRM=SI-DESTRUIR-<base> restore.sh [--db-only|--media-only] --from-restic <instantánea|latest>
#
# ⚠️ DESTRUCTIVO: recrea el esquema (pg_restore --clean) y REEMPLAZA los volúmenes de
#    medios. En producción, detén `web` (y worker/beat) antes, para evitar conexiones
#    activas mientras se recrea el esquema.
#
# Nada queda a medias. Primero se verifica todo; después los medios se preparan en una carpeta
# aparte dentro de cada volumen; la base se restaura en una sola transacción (si algo falla,
# queda como estaba) y solo entonces se sustituyen los medios. Un fallo antes de ese último
# paso deja la base y los medios como estaban.
set -eu

# Confirmación explícita: antes bastaba con invocarlo sin argumentos —`latest` era el valor por
# defecto— para arrasar la base y los medios de producción. Se exige nombrar la base que se va
# a destruir, para que no ocurra por inercia.
ESPERADO="SI-DESTRUIR-${POSTGRES_DB}"
if [ "${RESTORE_CONFIRM:-}" != "$ESPERADO" ]; then
  echo "✗ restore.sh DESTRUYE la base '${POSTGRES_DB}' y los volúmenes de medios."
  echo "  Para confirmar, repite el nombre de la base:"
  echo "      RESTORE_CONFIRM=$ESPERADO  restore.sh ${*:-latest}"
  exit 1
fi

DB=1
MEDIA=1
RESTIC=0
while [ $# -gt 0 ]; do
  case "$1" in
    --db-only) MEDIA=0 ;;
    --media-only) DB=0 ;;
    --from-restic) RESTIC=1 ;;
    -*) echo "✗ opción desconocida: $1"; exit 1 ;;
    *) break ;;
  esac
  shift
done
[ "$DB" = 1 ] || [ "$MEDIA" = 1 ] || { echo "✗ --db-only y --media-only se excluyen"; exit 1; }
TS="${1:-latest}"

# Lo preparado y no usado no se queda: ni la copia de restic ni los medios a medio sustituir.
WORK=""
cleanup() {
  [ -z "$WORK" ] || rm -rf "$WORK"
  rm -rf /volumes/media/.restaurando /volumes/private_media/.restaurando
}
trap cleanup EXIT INT TERM

if [ "$RESTIC" = 1 ]; then
  [ -n "${RESTIC_REPOSITORY:-}" ] || { echo "✗ --from-restic necesita RESTIC_REPOSITORY"; exit 1; }
  WORK=$(mktemp -d /backups/.restic-restore.XXXXXX)
  echo "→ restic restore $TS"
  restic restore "$TS" --host "${RESTIC_HOST:-resenas}" --tag resenas --target "$WORK"
  ORIGEN="restic ($TS)"
  DUMP="$WORK/backups/.restic/db.dump"
  MEDIA_SRC="$WORK/volumes/media"
  PRIVATE_SRC="$WORK/volumes/private_media"
else
  # Solo se restaura un respaldo completo: backup.sh deja OK dentro cuando lo verificó entero.
  if [ "$TS" = "latest" ]; then
    SRC=$(for dir in /backups/*/; do [ -f "${dir}OK" ] && echo "$dir"; done | sort -r | head -1)
  else
    SRC="/backups/$TS/"
  fi
  [ -n "${SRC:-}" ] && [ -d "$SRC" ] || { echo "✗ no existe el respaldo: ${SRC:-$TS}"; exit 1; }
  [ -f "$SRC/OK" ] || { echo "✗ el respaldo $SRC no está completo (le falta OK)"; exit 1; }
  ORIGEN="$SRC"
  DUMP="$SRC/db.dump"
  MEDIA_SRC="$SRC/media.tar.gz"
  PRIVATE_SRC="$SRC/private_media.tar.gz"
fi
echo "→ restaurando desde $ORIGEN"

# Un origen de medios es una carpeta (restic) o un tar.gz (respaldo local).
check_media() { # $1 = origen
  if [ -d "$1" ]; then return 0; fi
  [ -f "$1" ] || { echo "✗ falta $1"; exit 1; }
  tar tzf "$1" >/dev/null
}
stage() { # $1 = origen, $2 = volumen
  rm -rf "$2/.restaurando"
  mkdir "$2/.restaurando"
  if [ -d "$1" ]; then
    cp -a "$1/." "$2/.restaurando/"
  else
    tar xzf "$1" -C "$2/.restaurando"
  fi
}
swap() { # $1 = volumen
  find "$1" -mindepth 1 -maxdepth 1 ! -name .restaurando -exec rm -rf {} +
  find "$1/.restaurando" -mindepth 1 -maxdepth 1 -exec mv -t "$1" {} +
  rmdir "$1/.restaurando"
}

echo "→ verificando antes de tocar nada"
if [ "$DB" = 1 ]; then
  pg_restore --list "$DUMP" >/dev/null
fi
if [ "$MEDIA" = 1 ]; then
  check_media "$MEDIA_SRC"
  check_media "$PRIVATE_SRC"
  echo "→ preparando los medios"
  stage "$MEDIA_SRC" /volumes/media
  stage "$PRIVATE_SRC" /volumes/private_media
fi

if [ "$DB" = 1 ]; then
  echo "→ pg_restore en una sola transacción (si algo falla, la base queda como estaba)"
  PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
    -h "${POSTGRES_HOST:-db}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --clean --if-exists --no-owner --no-acl --single-transaction --exit-on-error "$DUMP"
fi

if [ "$MEDIA" = 1 ]; then
  echo "→ sustituyendo media y private_media"
  swap /volumes/media
  swap /volumes/private_media
fi

echo "✓ restauración completa desde $ORIGEN"
