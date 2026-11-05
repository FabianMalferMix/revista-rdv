#!/usr/bin/env bash
# mutar.sh — comprueba que una prueba FALLA cuando se rompe lo que vigila.
#
#   tools/ux/mutar.sh <archivo> <texto actual> <texto roto> <id de la prueba>
#   tools/ux/mutar.sh static/css/site.css 'container:filas / inline-size' 'container-type:normal' \
#       'tests/test_css_sistema.py::test_las_filas_se_disponen_segun_el_ancho_de_su_lista'
#
# <archivo> es relativo a backend/; lo de la raíz se nombra con ../ (../tools/ux/pages.txt).
#
# No toca el árbol de trabajo: copia HEAD en un worktree temporal de git, le pasa los cambios
# sin confirmar (también los archivos nuevos, así que se puede mutar una prueba que aún no
# tiene commit) y corre allí la prueba dos veces, cada una en un contenedor desechable de la
# imagen de desarrollo (resenas-app:dev) conectado a la base del stack (red resenas_default):
#   1. sin mutar, y tiene que pasar: una prueba que ya falla, o que se salta, no prueba nada;
#   2. con la PRIMERA aparición del texto actual cambiada por el roto, y tiene que fallar la
#      prueba misma: un error al prepararla no cuenta.
# Cada corrida recrea la base de pruebas (--create-db), que sale de las migraciones: así una
# migración mutada surte efecto. Esa base es solo de este guion (test_resenas_mutar), para no
# borrar la de una suite que esté corriendo, y dos mutar.sh a la vez se esperan el uno al otro.
# El contenedor corre con el usuario de quien llama, para que nada de lo que escriba en el
# worktree quede a nombre de root, y el worktree se borra al terminar, pase lo que pase.
#
# Sale con 0 si la prueba falla con la mutación, con 1 si NO detecta la regresión y con 2 si no
# llegó a ejecutarse (identificador mal escrito, error de sintaxis o de preparación) o si ya
# fallaba o se saltaba sin mutar: esos casos NO cuentan como detectada. Si algo no cuenta,
# enseña la salida de pytest.
set -uo pipefail
[ $# -eq 4 ] || { echo "uso: tools/ux/mutar.sh <archivo> <texto actual> <texto roto> <id de la prueba>"; exit 2; }
archivo="$1"
actual="$2"
roto="$3"
prueba="$4"
IMAGEN=resenas-app:dev
RED=resenas_default
BASE_MUTAR=resenas_mutar

raiz="$(git rev-parse --show-toplevel)" || exit 2
[ -f "$raiz/.env" ] || { echo "   ? falta $raiz/.env"; exit 2; }
docker image inspect "$IMAGEN" >/dev/null 2>&1 || { echo "   ? falta la imagen $IMAGEN: docker compose build web"; exit 2; }
docker network inspect "$RED" >/dev/null 2>&1 || { echo "   ? falta la red $RED: levanta la base con docker compose up -d db"; exit 2; }
[ "$actual" != "$roto" ] || { echo "   ? el texto roto es el mismo que el actual: no hay mutación"; exit 2; }

# Dos mutar.sh a la vez recrearían la misma base de pruebas: el segundo espera al primero.
if command -v flock >/dev/null; then
  exec 9>"${TMPDIR:-/tmp}/resenas-mutar.lock"
  flock -n 9 || { echo "   … espera a que termine otro mutar.sh"; flock 9; }
fi

temporal="$(mktemp -d)" || exit 2
arbol="$temporal/repo"
limpiar() {
  git -C "$raiz" worktree remove --force "$arbol" >/dev/null 2>&1
  rm -rf "$temporal"
  git -C "$raiz" worktree prune
}
trap limpiar EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

git -C "$raiz" worktree add --detach --quiet "$arbol" HEAD || exit 2
# Los cambios sin confirmar: los de los archivos con seguimiento, como parche contra HEAD, y
# los archivos nuevos que git no ignora, copiados tal cual.
if ! git -C "$raiz" diff --quiet HEAD; then
  git -C "$raiz" diff --binary --no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ HEAD \
    | git -C "$arbol" apply --binary || { echo "   ? no se pudieron copiar los cambios sin confirmar"; exit 2; }
fi
git -C "$raiz" ls-files --others --exclude-standard -z \
  | tar -C "$raiz" --null -T - -cf - | tar -C "$arbol" -xf - || { echo "   ? no se pudieron copiar los archivos nuevos"; exit 2; }

destino="$(realpath -m "$arbol/backend/$archivo")"
case "$destino" in
  "$(realpath "$arbol")"/*) ;;
  *) echo "   ? backend/$archivo queda fuera del repositorio"; exit 2 ;;
esac
[ -f "$destino" ] || { echo "   ? no existe backend/$archivo (o git lo ignora)"; exit 2; }

# `mutar comprobar` solo mira que el texto actual esté; `mutar aplicar` cambia su primera
# aparición por el roto.
mutar() {
  python3 - "$destino" "$actual" "$roto" "backend/$archivo" "$1" <<'PY'
import sys

ruta, actual, roto, nombre, modo = sys.argv[1:6]
texto = open(ruta, encoding="utf-8").read()
if actual not in texto:
    sys.exit(f"   ? el texto a mutar no está en {nombre}: {actual[:70]!r}")
if modo == "aplicar":
    open(ruta, "w", encoding="utf-8").write(texto.replace(actual, roto, 1))
PY
}
mutar comprobar || exit 2

correr() {
  # Sin el descriptor del candado: el contenedor no lo hereda.
  docker run --rm --env-file "$raiz/.env" --network "$RED" \
    --user "$(id -u):$(id -g)" -e HOME=/tmp -e POSTGRES_DB="$BASE_MUTAR" \
    -v "$arbol":/repo -w /repo/backend "$IMAGEN" \
    pytest "$prueba" -p no:cacheprovider -p no:randomly --create-db >"$temporal/salida.txt" 2>&1 9>&-
  codigo=$?
  # La última línea de recuento de pytest: «1 passed in 0.52s», «1 failed, 1 error in …».
  resumen="$(grep -E '[0-9]+ (passed|failed|errors?|skipped|xfailed|xpassed)|no tests ran' "$temporal/salida.txt" | tail -n 1)"
}
mostrar() {
  echo "   --- salida de pytest ---"
  cat "$temporal/salida.txt"
}

correr
case "$codigo" in
  0) if [[ "$resumen" == *skipped* ]]; then
       echo "   ? la prueba se salta sin mutar ($resumen): no vigila nada: $prueba"; mostrar; exit 2
     fi ;;
  1) echo "   ? la prueba ya falla sin mutar ($resumen): así no prueba nada: $prueba"; mostrar; exit 2 ;;
  5) echo "   ? ninguna prueba responde a ese identificador: $prueba"; exit 2 ;;
  *) echo "   ? la prueba no llegó a ejecutarse sin mutar (pytest salió con $codigo): $prueba"; mostrar; exit 2 ;;
esac
echo "   · sin mutar pasa ($resumen)"

mutar aplicar || exit 2
correr
case "$codigo" in
  # Cuenta como detectada si falla la prueba misma. Un error al prepararla no cuenta: la prueba
  # no llegó a mirar nada. Un error al recogerla, tras el fallo, sí: la mutación dejó algo que
  # su limpieza no deshace (una migración que ya no vuelve atrás, por ejemplo).
  1) if [[ "$resumen" != *failed* ]] || grep -q "ERROR at setup of" "$temporal/salida.txt"; then
       echo "   ? con la mutación falla la preparación, no la prueba ($resumen): no cuenta: $prueba"; mostrar; exit 2
     fi
     nota=""
     [[ "$resumen" == *error* ]] && nota=" (y su limpieza tampoco termina)"
     echo "   ✓ falla como debe ($resumen)$nota: ${prueba##*::}" ;;
  0) echo "   ✗ NO detecta la regresión ($resumen): $prueba"; exit 1 ;;
  *) echo "   ? la prueba no llegó a ejecutarse con la mutación (pytest salió con $codigo): $prueba"; mostrar; exit 2 ;;
esac
