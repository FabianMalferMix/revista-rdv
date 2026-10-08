#!/usr/bin/env bash
# mutar.sh — comprueba que una prueba FALLA cuando se rompe lo que vigila.
#
#   tools/ux/mutar.sh <archivo> <texto actual> <texto roto> <id de la prueba>
#   tools/ux/mutar.sh static/css/site.css 'container:filas / inline-size' 'container-type:normal' \
#       'tests/test_css_sistema.py::test_las_filas_se_disponen_segun_el_ancho_de_su_lista'
#
# <archivo> es relativo a backend/. Sustituye la PRIMERA aparición del texto, corre la
# prueba dentro del contenedor `web` (que debe estar arriba) y restaura el archivo pase lo
# que pase. Una prueba nueva que sigue en verde con la regresión dentro no vigila nada.
#
# Sale con 0 si la prueba falla como debe, con 1 si NO detecta la regresión y con 2 si la
# prueba ni siquiera llegó a ejecutarse (identificador mal escrito, error de sintaxis en
# la mutación): ese caso NO cuenta como detectada.
set -uo pipefail
[ $# -eq 4 ] || { echo "uso: tools/ux/mutar.sh <archivo> <texto actual> <texto roto> <id de la prueba>"; exit 2; }
cd "$(git rev-parse --show-toplevel)/backend" || exit 2
COMPOSE="${COMPOSE:-docker compose}"
archivo="$1"
[ -f "$archivo" ] || { echo "no existe backend/$archivo"; exit 2; }
copia="$(mktemp)"
cp "$archivo" "$copia"

restaurar() {
  cp "$copia" "$archivo"
  rm -f "$copia"
  # Un .py mutado y restaurado en pocos segundos puede dejar al servidor de desarrollo con
  # el código MUTADO: el recargador reinicia con la mutación y toma su foto de fechas
  # después de la restauración, así que no ve ningún cambio. Se le obliga a recargar.
  case "$archivo" in *.py) sleep 3; touch "$archivo" ;; esac
}
trap restaurar EXIT

python3 - "$archivo" "$2" "$3" <<'PY' || exit 2
import sys

ruta, actual, roto = sys.argv[1:4]
texto = open(ruta, encoding="utf-8").read()
if actual not in texto:
    sys.exit(f"   ? el texto a mutar no está en {ruta}: {actual[:70]!r}")
open(ruta, "w", encoding="utf-8").write(texto.replace(actual, roto, 1))
PY

$COMPOSE exec -T web pytest "$4" -q -p no:cacheprovider >/dev/null 2>&1
codigo=$?
case "$codigo" in
  1) echo "   ✓ falla como debe: ${4##*::}" ;;
  0) echo "   ✗ NO detecta la regresión: $4"; exit 1 ;;
  *) echo "   ? la prueba no llegó a ejecutarse (pytest salió con $codigo): $4"; exit 2 ;;
esac
