#!/usr/bin/env python3
"""Cuenta, archivo por archivo, los identificadores de decisión, de ticket y de sesión
que hay en el código, y falla si alguno crece.

La regla («Reglas del código» en CONTRIBUTING.md): la historia y los códigos de decisión
van en el mensaje del commit, no en el código. Los que ya estaban quedan en una línea
base que solo puede bajar.

    python3 tools/ci/decision_refs.py            # comprueba (lo corre pre-commit)
    python3 tools/ci/decision_refs.py --update   # baja la línea base tras quitar algunos

Si un archivo suma identificadores, la comprobación falla y los muestra. Si resta, también
falla, para que el PR baje la línea base con --update y no quede margen para volver a subir.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("decision_refs_baseline.json")

# Códigos de decisión (D18, C5) y de ticket (B07), hallazgos y sesiones de auditorías
# anteriores (S-33, qa-23), pasos, lotes y tickets de planes, y números de PR.
PATTERN = re.compile(
    r"\b[DC]\d{1,2}\b"
    r"|\bB\d{2}\b"
    r"|\bS-\d{2}\b"
    r"|\bqa-\d+\b"
    r"|\b(?:[Tt]icket|[Pp]aso|[Ll]ote)\s+(?:\d|[A-H]\b)"
    r"|\b[Hh]allazgos?\b"
    r"|\bPR\s*#\d+"
)

# La documentación, las migraciones, los datos y lo de terceros pueden citarlos; el código no.
# pyproject.toml nombra reglas de ruff (C4, C90…), que no son decisiones.
EXCLUDED = re.compile(
    r"\.md$"
    r"|(?:^|/)pyproject\.toml$"
    r"|/migrations/"
    r"|^backend/static/vendor/"
    r"|^backend/datos_de_desarrollo/"
    r"|^tools/ux/(?:linea-base|final)/"
    r"|^tools/ci/decision_refs"
)


def tracked_files():
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [name for name in listing.split("\0") if name and not EXCLUDED.search(name)]


def find_refs(path):
    try:
        text = (ROOT / path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        return []
    return [
        (number, match.group(0), line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        for match in PATTERN.finditer(line)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--update", action="store_true", help="baja la línea base")
    args = parser.parse_args()

    refs = {path: found for path in tracked_files() if (found := find_refs(path))}
    current = {path: len(found) for path, found in refs.items()}
    if not BASELINE.exists():
        baseline = None
    else:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    if baseline is not None:
        grown = {p: n for p, n in current.items() if n > baseline.get(p, 0)}
        if grown:
            print(
                "Identificadores de decisión, de ticket o de sesión nuevos en el código."
            )
            print(
                "Esa historia va en el mensaje del commit. Si el archivo solo se renombró,"
            )
            print(f"renombra también su entrada en {BASELINE.relative_to(ROOT)}.\n")
            for path, count in sorted(grown.items()):
                print(f"{path}: {count} (la línea base admite {baseline.get(path, 0)})")
                for number, token, line in refs[path]:
                    print(f"  {path}:{number}: «{token}» en: {line[:100]}")
            return 1

    if args.update or baseline is None:
        content = json.dumps(
            dict(sorted(current.items())), ensure_ascii=False, indent=2
        )
        BASELINE.write_text(content + "\n", encoding="utf-8")
        print(
            f"Línea base: {sum(current.values())} identificadores en {len(current)} archivos."
        )
        return 0

    stale = {p: n for p, n in baseline.items() if current.get(p, 0) < n}
    if stale:
        print("La línea base quedó por encima de lo que hay. Bájala con")
        print("  python3 tools/ci/decision_refs.py --update")
        for path, count in sorted(stale.items()):
            print(f"  {path}: {current.get(path, 0)} (la línea base dice {count})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
