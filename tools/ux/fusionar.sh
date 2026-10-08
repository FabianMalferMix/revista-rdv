#!/usr/bin/env bash
# fusionar.sh — cierra un paso del plan: fusiona su PR solo si el CI está verde.
#
#   tools/ux/fusionar.sh <n.º de PR> <rama> "<efecto visible>" ["<cuerpo del merge>"]
#   tools/ux/fusionar.sh 105 ux-2-2-indices-y-rejillas "los índices son filas y las rejillas reparten el ancho"
#
# Hace lo que pide §0 del backlog, en este orden:
#   1. exige que el PR esté limpio y con TODAS sus comprobaciones en verde;
#   2. fusiona sin fast-forward con el asunto «Merge <rama> — <efecto> (#n)», y deja que
#      GitHub borre la rama remota (nunca `git push --delete`);
#   3. trae `main`, borra la rama local y te deja en `main` al día.
# No comprueba el CI de `main` después del merge: eso se mira aparte, antes de abrir el
# siguiente paso (`gh run list --branch main --limit 1`).
#
# El cuerpo del merge es opcional (cuarto argumento o variable CUERPO_MERGE): ahí va la
# línea de atribución que indique tu sesión, si la hay.
set -euo pipefail
[ $# -ge 3 ] || { echo 'uso: tools/ux/fusionar.sh <n.º de PR> <rama> "<efecto visible>" ["<cuerpo del merge>"]'; exit 2; }
cd "$(git rev-parse --show-toplevel)"
pr="$1"; rama="$2"; efecto="$3"; cuerpo="${4:-${CUERPO_MERGE:-}}"

estado=$(gh pr view "$pr" --json mergeStateStatus,statusCheckRollup \
  -q '.mergeStateStatus + " " + ([.statusCheckRollup[] | .conclusion] | unique | join(","))')
echo "PR #$pr: $estado"
[[ "$estado" == "CLEAN SUCCESS" ]] || { echo "NO se fusiona: el CI no está verde o el PR no está limpio"; exit 1; }

gh pr merge "$pr" --merge --delete-branch --subject "Merge $rama — $efecto (#$pr)" --body "$cuerpo" >/dev/null 2>&1 || true
[[ "$(gh pr view "$pr" --json state -q .state)" == "MERGED" ]] || { echo "el PR no quedó fusionado"; exit 1; }

git fetch -q --prune origin
[[ "$(git branch --show-current)" == "main" ]] || git checkout -q main
git merge -q --ff-only origin/main
git branch -D "$rama" >/dev/null 2>&1 || true
echo "fusionado. main: $(git log --oneline -1)"
