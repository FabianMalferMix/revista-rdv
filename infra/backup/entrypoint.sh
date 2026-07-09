#!/usr/bin/env sh
# Bucle del sidecar de respaldos (perfil "backup"). Ejecuta backup.sh cada
# BACKUP_INTERVAL_SECONDS. Para respaldos on-demand, correr backup.sh directamente.
set -eu
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
echo "sidecar de respaldos activo (cada ${INTERVAL}s)"
while true; do
  sh /scripts/backup.sh || echo "✗ el respaldo falló (se reintenta en el próximo ciclo)"
  sleep "$INTERVAL"
done
