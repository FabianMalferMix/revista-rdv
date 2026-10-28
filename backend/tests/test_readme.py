"""La «Estructura» del README es el mapa del repositorio: qué apps hay y dónde vive cada cosa.

Una app instalada sin anotar o una carpeta que ya no existe lo vuelven un mapa falso, y es lo
primero que se lee. Estas pruebas lo comparan con `INSTALLED_APPS` y con el árbol real.

DÓNDE CORREN: en el CI, que hace checkout del repositorio completo y lanza pytest desde
`backend/`, de modo que la raíz queda accesible. En el contenedor de desarrollo se SALTAN,
porque solo monta `backend/` y el README no existe ahí.
"""

import re
from pathlib import Path

import pytest
from django.apps import apps

REPO_ROOT = Path(__file__).resolve().parents[2]


def _structure_paths():
    """Las rutas del bloque «Estructura», reconstruidas por su sangría (dos espacios)."""
    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        pytest.skip("README.md no existe en este árbol")
    text = readme.read_text(encoding="utf-8")
    block = re.search(r"^## Estructura\n.*?^```text\n(.*?)^```", text, re.S | re.M)
    assert block, "el README ya no tiene el bloque de «Estructura»"
    paths, stack = [], []
    for line in block.group(1).splitlines():
        if not line.strip():
            continue
        depth = (len(line) - len(line.lstrip(" "))) // 2
        stack[depth:] = [line.split()[0].rstrip("/")]
        paths.append("/".join(stack))
    return paths


def test_readme_structure_lists_every_installed_app():
    installed = {
        config.name.removeprefix("apps.")
        for config in apps.get_app_configs()
        if config.name.startswith("apps.")
    }
    listed = {
        path.removeprefix("backend/apps/")
        for path in _structure_paths()
        if path.startswith("backend/apps/")
    }
    assert installed, "no se encontró ninguna app del proyecto en INSTALLED_APPS"
    assert listed == installed, (
        f"instaladas sin anotar en el README: {sorted(installed - listed)}; "
        f"anotadas sin estar instaladas: {sorted(listed - installed)}"
    )


def test_readme_structure_only_names_paths_that_exist():
    paths = _structure_paths()
    # Control: el bloque se leyó entero, no una lista vacía que pasaría sin mirar nada.
    assert {"backend/apps/content", "infra/caddy", "tools/ci"} <= set(paths)
    missing = [path for path in paths if not (REPO_ROOT / path).exists()]
    assert missing == [], f"el README nombra rutas que no existen: {missing}"
