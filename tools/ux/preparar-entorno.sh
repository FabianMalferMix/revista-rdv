#!/usr/bin/env bash
# preparar-entorno.sh — deja una máquina nueva lista para trabajar sobre el diseño, con los mismos
# datos con que se diseñó y se midió cada paso.
#
#   tools/ux/preparar-entorno.sh
#
# La base de datos y los medios NO viajan con el repositorio; su copia sí
# (backend/datos_de_desarrollo/). Este guion:
#   1. comprueba los requisitos y crea el .env desde .env.example si falta;
#   2. levanta los contenedores y espera al sitio;
#   3. puebla la base con `datos_de_desarrollo cargar`, el mismo comando que usan el README y el
#      job navegador del CI: la copia, la identidad del colectivo y las copias de las imágenes;
#   4. instala las dependencias de tools/ux;
#   5. pasa la prueba de humo.
#
# Se puede repetir: en un entorno ya preparado no cambia nada, porque `cargar` deja como está una
# base de desarrollo que ya tiene contenido. Solo para desarrollo: `cargar` se niega a correr con
# DJANGO_DEBUG=0 o donde el entorno se declara de producción.
#
# Variables: COMPOSE (por defecto «docker compose») y UX_BASE (http://localhost:8000).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
COMPOSE="${COMPOSE:-docker compose}"
BASE="${UX_BASE:-http://localhost:8000}"
CHROME_BIN="${CHROME:-/usr/bin/google-chrome}"

paso() { printf '\n── %s\n' "$*"; }

paso "1/5 Requisitos"
for bin in docker node npm python3 curl git; do
  command -v "$bin" >/dev/null || { echo "falta «$bin» en esta máquina"; exit 1; }
done
[ -x "$CHROME_BIN" ] || echo "aviso: no hay Chrome en $CHROME_BIN. Exporta CHROME=/ruta/al/chrome antes de usar capture.js"
command -v gh >/dev/null || echo "aviso: falta gh (GitHub CLI). Hace falta para abrir y fusionar los PR"
[ -f .env ] || { cp .env.example .env; echo ".env creado desde .env.example"; }

paso "2/5 Contenedores"
$COMPOSE up -d --build
printf 'esperando a %s ' "$BASE"
for _ in $(seq 1 90); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/healthz/" || true)" = "200" ] && break
  printf '.'; sleep 2
done
echo
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/healthz/" || true)" = "200" ] || {
  echo "el sitio no responde en $BASE. Mira «$COMPOSE logs web»"; exit 1; }

paso "3/5 Datos de desarrollo"
# El único camino para poblar desarrollo (ver el README): en una base recién creada carga la copia
# de backend/datos_de_desarrollo/ con la identidad del colectivo; en una de desarrollo que ya
# tiene contenido no hace nada, y fuera de desarrollo se niega.
$COMPOSE exec -T web python manage.py datos_de_desarrollo cargar

paso "4/5 Herramienta de capturas"
[ -d tools/ux/node_modules/playwright-core ] || npm --prefix tools/ux install --no-audit --no-fund

paso "5/5 Humo"
python3 tools/ux/smoke.py "$BASE"

cat <<FIN

Entorno listo en $BASE.
Para entrar al panel, crea tu cuenta: $COMPOSE exec web python manage.py createsuperuser
Siguiente: el trabajo pendiente está en docs/backlog-codigo.md.
FIN
