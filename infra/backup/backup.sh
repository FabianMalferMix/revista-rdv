#!/usr/bin/env sh
# Respaldo del archivo: dump de PostgreSQL (formato custom) + tar de media/private_media,
# con sincronización OFF-SITE opcional (restic) y ALERTA de fallo (ping healthchecks).
# Se ejecuta dentro de un contenedor con pg_dump/restic/curl y acceso a los volúmenes.
#
# Un respaldo solo cuenta si se verificó entero: se escribe en <fecha>.partial, se comprueba
# (pg_restore --list y gzip -t) y solo entonces pasa a <fecha>, con un archivo OK dentro. La
# rotación y `restore.sh latest` miran únicamente los respaldos con OK, y cualquier fallo
# aborta el script (set -e) y dispara el ping de fallo.
set -eu

# Los artefactos que genera este script contienen la BASE DE DATOS COMPLETA (correos de
# suscriptores, PII de envíos, hashes de contraseñas) y los MANUSCRITOS privados. Sin
# umask quedaban 0644 en un bind-mount del host, legibles por cualquier usuario local.
# 077 los deja 0600 y los directorios 0700.
umask 077

# ── Alerta de fallo (dead-man's-switch tipo healthchecks.io) ──
# Si BACKUP_PING_URL está definido: se hace GET a esa URL al terminar OK, y a
# "<URL>/fail" si el respaldo aborta por cualquier motivo (set -e + trap EXIT).
PING="${BACKUP_PING_URL:-}"
notify_fail() {
  [ -n "$PING" ] && curl -fsS -m 10 --retry 3 --retry-connrefused "${PING%/}/fail" >/dev/null 2>&1 || true
}
trap notify_fail EXIT INT TERM

# Un volumen que no se montó llega vacío (Docker crea uno nuevo) y tar lo archiva sin quejarse:
# por debajo del mínimo de archivos, el respaldo falla en vez de guardar «nada».
require_files() { # $1 = directorio, $2 = mínimo de archivos
  [ -d "$1" ] || { echo "✗ $1 no es un directorio: ¿está montado el volumen?" >&2; exit 1; }
  found=$(find "$1" -type f | head -n "$2" | wc -l)
  if [ "$found" -lt "$2" ]; then
    echo "✗ $1 tiene $found archivos y el mínimo es $2: ¿está montado el volumen?" >&2
    exit 1
  fi
}

# GNU tar sale con 1 si un archivo cambió mientras lo leía: el archivo que deja es válido, así
# que se avisa y se sigue. Con 2 o más (lectura imposible, disco lleno) el respaldo falla.
archive() { # $1 = directorio, $2 = archivo de salida
  rc=0
  tar czf "$2" -C "$1" . || rc=$?
  if [ "$rc" -eq 1 ]; then
    echo "  (aviso: algún archivo de $1 cambió durante la copia)"
  elif [ "$rc" -ne 0 ]; then
    echo "✗ tar falló (código $rc) al archivar $1" >&2
    exit "$rc"
  fi
  gzip -t "$2"
}

# Los respaldos completos, del más reciente al más antiguo (el nombre es la fecha).
complete_backups() {
  for dir in /backups/*/; do
    [ -f "${dir}OK" ] && echo "$dir"
  done | sort -r
}

TS=$(date +%Y%m%d-%H%M%S)
DEST="/backups/$TS"
PARTIAL="$DEST.partial"
# Lo que dejó a medias una corrida anterior nunca fue un respaldo válido.
find /backups -mindepth 1 -maxdepth 1 -type d -name '*.partial' -mmin +60 -exec rm -rf {} +
mkdir -p "$PARTIAL"
# Explícito además del umask: si /backups viene de un bind-mount con permisos laxos,
# al menos el directorio del respaldo queda cerrado.
chmod 700 "$PARTIAL"

echo "→ pg_dump de '$POSTGRES_DB'"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "${POSTGRES_HOST:-db}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --format=custom --file="$PARTIAL/db.dump"
pg_restore --list "$PARTIAL/db.dump" >/dev/null

echo "→ archivando volúmenes de medios"
require_files /volumes/media "${BACKUP_MIN_MEDIA_FILES:-1}"
require_files /volumes/private_media "${BACKUP_MIN_PRIVATE_FILES:-0}"
archive /volumes/media "$PARTIAL/media.tar.gz"
archive /volumes/private_media "$PARTIAL/private_media.tar.gz"

# Verificado entero: pasa a su nombre definitivo, con la marca de completo.
touch "$PARTIAL/OK"
mv "$PARTIAL" "$DEST"

# ── Off-site (opcional pero recomendado) ──
# Con RESTIC_REPOSITORY + RESTIC_PASSWORD definidos, sube el respaldo a almacenamiento
# externo cifrado y deduplicado (S3/BackBlaze/rclone/… según el backend de restic).
# Sin RESTIC_REPOSITORY el paso se omite (un respaldo solo local NO protege ante la
# pérdida del host).
if [ -n "${RESTIC_REPOSITORY:-}" ]; then
  echo "→ off-site (restic → $RESTIC_REPOSITORY)"
  restic snapshots >/dev/null 2>&1 || restic init          # inicializa el repo la 1ª vez
  restic backup --tag resenas --host "${RESTIC_HOST:-resenas}" "$DEST"
  restic forget --prune --keep-last "${RESTIC_KEEP:-30}" >/dev/null
else
  echo "  (off-site desactivado: define RESTIC_REPOSITORY para activarlo)"
fi

# Retención local: los últimos BACKUP_KEEP respaldos completos.
KEEP="${BACKUP_KEEP:-14}"
complete_backups | tail -n "+$((KEEP + 1))" | while read -r old; do
  echo "→ purgando respaldo antiguo: $old"
  rm -rf "$old"
done

echo "✓ respaldo completo en $DEST ($(du -sh "$DEST" 2>/dev/null | cut -f1))"

# Éxito: desarma el trap de fallo y avisa OK.
trap - EXIT INT TERM
[ -n "$PING" ] && curl -fsS -m 10 --retry 3 --retry-connrefused "$PING" >/dev/null 2>&1 || true
