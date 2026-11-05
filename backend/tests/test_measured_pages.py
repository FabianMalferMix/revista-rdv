"""Las páginas que miden las herramientas de tools/ux/ están en los datos de desarrollo.

capture.js, browser-smoke.js y contraste.js recorren tools/ux/pages.txt contra el sitio de
desarrollo poblado con backend/datos_de_desarrollo/datos.json. Una ruta que nombra una ficha que
no está en esa copia da 404, y la herramienta no tiene nada que medir.

Leen tools/ux/pages.txt, en la raíz del repositorio: corren en el CI y con el repositorio montado,
y se saltan en el contenedor de desarrollo, que solo monta backend/.
"""

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.core import serializers
from django.urls import Resolver404, resolve

from apps.content.management.commands.datos_de_desarrollo import CARPETA

PAGES = Path(__file__).resolve().parents[2] / "tools" / "ux" / "pages.txt"


def _routes():
    """Las rutas de pages.txt: una página por línea, «nombre ruta [ancho]»; # comenta."""
    if not PAGES.exists():
        pytest.skip("tools/ux/pages.txt vive en la raíz del repositorio, fuera del contenedor")
    lines = (line.strip() for line in PAGES.read_text(encoding="utf-8").splitlines())
    return [line.split()[1] for line in lines if line and not line.startswith("#")]


def _addresses_in_development_data():
    """La dirección de cada ficha de datos.json, la que da su modelo con get_absolute_url: así
    una ficha se reconoce por su modelo y su slug juntos, como la busca la vista."""
    rows = serializers.deserialize("json", (CARPETA / "datos.json").read_text(encoding="utf-8"))
    return {
        row.object.get_absolute_url() for row in rows if hasattr(row.object, "get_absolute_url")
    }


def test_every_page_the_tools_measure_exists_in_the_development_data():
    routes, addresses = _routes(), _addresses_in_development_data()
    problems, with_object = [], []
    for route in routes:
        path = urlsplit(route).path
        try:
            match = resolve(path)
        except Resolver404:
            problems.append(f"{route}: no es una dirección del sitio")
            continue
        # Un índice no nombra ninguna ficha: basta con que la ruta exista.
        if not match.kwargs:
            continue
        with_object.append(route)
        if path not in addresses:
            problems.append(
                f"{route}: ninguna ficha de datos.json está en esa dirección "
                f"({', '.join(f'{k}={v}' for k, v in match.kwargs.items())})"
            )
    missing = "\n".join(problems)
    assert not problems, f"pages.txt nombra páginas que el sitio de desarrollo no tiene:\n{missing}"
    # Control: se leyó la lista entera, y tiene fichas que se encontraron en los datos, no solo
    # índices, que pasarían sin mirarlos.
    assert len(routes) >= 10 and with_object
