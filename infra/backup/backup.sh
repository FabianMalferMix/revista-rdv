#!/usr/bin/env sh
# Respaldo del archivo: dump de PostgreSQL (formato custom) + tar de media/private_media,
# con sincronización OFF-SITE opcional (restic) y ALERTA de fallo (ping healthchecks).
# Se ejecuta dentro de un contenedor con pg_dump/restic/curl y acceso a los volúmenes.
set -eu

# Los artefactos que genera este script contienen la BASE DE DATOS COMPLETA (correos de
# suscriptores, PII de envíos, hashes de contraseñas) y los MANUSCRITOS privados. Sin
# umask quedaban 0644 en un bind-mount del host, legibles por cualquier usuario local
# (hallazgo S-06). 077 los deja 0600 y los directorios 0700.
umask 077

# ── Alerta de fallo (dead-man's-switch tipo healthchecks.io) ──
# Si BACKUP_PING_URL está definido: se hace GET a esa URL al terminar OK, y a
# "<URL>/fail" si el respaldo aborta por cualquier motivo (set -e + trap EXIT).
PING="${BACKUP_PING_URL:-}"
notify_fail() {
  [ -n "$PING" ] && curl -fsS -m 10 --retry 3 "${PING%/}/fail" >/dev/null 2>&1 || true
}
trap notify_fail EXIT INT TERM

TS=$(date +%Y%m%d-%H%M%S)
DEST="/backups/$TS"
mkdir -p "$DEST"
# Explícito además del umask: si /backups viene de un bind-mount con permisos laxos,
# al menos el directorio del respaldo queda cerrado.
chmod 700 "$DEST"

echo "→ pg_dump de '$POSTGRES_DB'"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "${POSTGRES_HOST:-db}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --format=custom --file="$DEST/db.dump"

echo "→ archivando volúmenes de medios"
tar czf "$DEST/media.tar.gz" -C /volumes/media . 2>/dev/null || echo "  (media vacío)"
tar czf "$DEST/private_media.tar.gz" -C /volumes/private_media . 2>/dev/null || echo "  (private_media vacío)"

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

# Retención local: conservar los últimos BACKUP_KEEP respaldos (rotación diaria simple).
KEEP="${BACKUP_KEEP:-14}"
ls -1dt /backups/*/ 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r old; do
  echo "→ purgando respaldo antiguo: $old"
  rm -rf "$old"
done

echo "✓ respaldo completo en $DEST ($(du -sh "$DEST" 2>/dev/null | cut -f1))"

# Éxito: desarma el trap de fallo y avisa OK.
trap - EXIT INT TERM
[ -n "$PING" ] && curl -fsS -m 10 --retry 3 "$PING" >/dev/null 2>&1 || true
