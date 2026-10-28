#!/usr/bin/env bash
# Comprueba la sintaxis de los guiones propios con node --check. node solo lee el primer
# archivo que recibe, así que este guion recorre uno a uno los que le pasa pre-commit.
set -euo pipefail
status=0
for file in "$@"; do
  node --check "$file" || status=1
done
exit "$status"
