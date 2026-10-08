#!/usr/bin/env bash
# preparar-entorno.sh — deja una máquina nueva lista para seguir el plan de UX/UI
# (docs/plan-ejecucion-ux.md, sección «Preparar un entorno nuevo»).
#
#   tools/ux/preparar-entorno.sh
#
# La base de datos y los medios NO viajan con el repositorio. Este guion reconstruye el
# estado con el que se diseñó y se midió cada paso:
#   1. contenido de demostración (`seed_demo`), solo si la base está vacía;
#   2. la identidad real del colectivo (docs/tarea-identidad-del-sitio.md §3);
#   3. integrantes de relleno hasta 12, que es el umbral desde el que la portada monta
#      la cinta (UMBRAL_CINTA en apps/content/views.py);
#   4. el material visual genérico (`seed_material_generico`);
#   5. las dependencias de tools/ux y una pasada de humo.
#
# Es IDEMPOTENTE: en un entorno ya preparado no cambia nada. Y es prudente: `seed_demo`
# reescribe el perfil del sitio, así que solo se ejecuta sobre una base sin artículos.
# Solo para desarrollo: se niega a correr con DJANGO_DEBUG=0.
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

paso "3/5 Contenido, identidad e integrantes"
$COMPOSE exec -T web python - <<'PY'
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402

from apps.content.models import Article  # noqa: E402
from apps.people.models import Contributor  # noqa: E402
from apps.showcase.models import SiteProfile, SiteSocialLink  # noqa: E402

if not settings.DEBUG:
    raise SystemExit("Este guion es solo para desarrollo (DJANGO_DEBUG=1).")

NOMBRE = "Repitentes del Verso"
perfil = SiteProfile.load()

# 1. Demostración: solo en una base vacía. `seed_demo` reescribe el perfil del sitio.
if Article.objects.exists():
    print("contenido: ya hay artículos, no se ejecuta seed_demo")
elif perfil.name == NOMBRE:
    raise SystemExit(
        "El perfil ya lleva la identidad real pero no hay artículos: estado inesperado. "
        "No se ejecuta seed_demo para no pisar el perfil; revísalo a mano."
    )
else:
    print("contenido: base vacía, se ejecuta seed_demo (apunta la contraseña que imprime)")
    call_command("seed_demo")
    perfil = SiteProfile.load()

# 2. Identidad real: los valores de docs/tarea-identidad-del-sitio.md §3.
if perfil.name == NOMBRE:
    print(f"identidad: ya aplicada ({perfil.name} — {perfil.tagline})")
else:
    perfil.name = NOMBRE
    perfil.tagline = "Colectivo de poesía"
    perfil.founded_year = 2023
    perfil.general_email = "repitentesdelverso@gmail.com"
    perfil.location = "Chile"
    # seed_demo pone un correo de gestión en un dominio que no es del colectivo.
    perfil.booking_email = ""
    perfil.save()
    SiteSocialLink.objects.filter(profile=perfil).delete()
    SiteSocialLink.objects.create(
        profile=perfil,
        platform="Instagram",
        url="https://www.instagram.com/repitentesdelverso",
        position=0,
    )
    print(f"identidad: aplicada ({perfil.name} — {perfil.tagline})")

# 3. Integrantes de relleno hasta el umbral de la cinta.
RELLENO = [
    ("Camila Reyes", "Poeta"),
    ("Tomás Figueroa", "Poeta · taller"),
    ("Javiera Núñez", "Poeta"),
    ("Matías Olivares", "Poeta · edición"),
    ("Antonia Vergara", "Poeta"),
    ("Ignacio Bravo", "Poeta · gestión"),
    ("Rocío Carrasco", "Poeta"),
    ("Felipe Astorga", "Poeta"),
    ("Valentina Aguirre", "Poeta · taller"),
]
activos = Contributor.objects.filter(is_member=True, active=True)
creados = 0
for i, (nombre, rol) in enumerate(RELLENO):
    if activos.count() >= 12:
        break
    _, nuevo = Contributor.objects.get_or_create(
        slug=f"relleno-{i}",
        defaults={
            "display_name": nombre,
            "role": rol,
            "position": 10 + i,
            "is_member": True,
            "active": True,
            "short_bio": "Integrante de relleno para probar la cinta.",
        },
    )
    creados += nuevo
print(f"integrantes: {activos.count()} activos ({creados} de relleno creados ahora)")

# 4. Material visual genérico: idempotente, nunca pisa material real.
call_command("seed_material_generico")
PY

paso "4/5 Herramienta de capturas"
[ -d tools/ux/node_modules/playwright-core ] || npm --prefix tools/ux install --no-audit --no-fund

paso "5/5 Humo"
python3 tools/ux/smoke.py "$BASE"

cat <<FIN

Entorno listo en $BASE.
Siguiente: abre docs/plan-ejecucion-ux.md y empieza por «Dónde estamos».
FIN
