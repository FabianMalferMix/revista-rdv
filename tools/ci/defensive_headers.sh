#!/usr/bin/env bash
# Comprueba las cabeceras defensivas de un archivo que Caddy sirve del volumen de medios: lo de
# /media/ y lo que Django entrega por X-Accel-Redirect (el audio de un registro publicado, el PDF
# de una publicación). Esas respuestas no pasan por Django, así que ni su SecurityMiddleware ni
# config.csp las tocan: las cabeceras salen de infra/caddy/Caddyfile, y aquí se comprueban con el
# Caddy de producción delante (job prod-runtime del CI).
#
#   curl -fsS -D - -o /dev/null "$URL" | tools/ci/defensive_headers.sh "<qué se sirve>"
#
# Lee las cabeceras de la respuesta en la entrada. Sale con 1 si falta alguna o llega con otro
# valor, y entonces enseña las que llegaron.
set -uo pipefail
[ $# -eq 1 ] || { echo "uso: curl -fsS -D - -o /dev/null URL | $0 '<qué se sirve>'"; exit 2; }
headers="$(tr -d '\r')"
status=0
for expected in \
  "X-Content-Type-Options: nosniff" \
  "Content-Security-Policy: default-src 'none'; sandbox" \
  "Referrer-Policy: no-referrer" \
  "X-Frame-Options: DENY"; do
  grep -qiFx -- "$expected" <<<"$headers" \
    || { echo "FALLO: $1 se sirve sin «$expected»"; status=1; }
done
if [ "$status" != 0 ]; then
  printf '%s\n' "$headers"
  exit 1
fi
echo "OK: $1 se sirve con nosniff, la CSP de aislamiento, sin referente y sin marcos"
