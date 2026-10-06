"""La hoja de estilos no se queda cacheada en desarrollo.

En producción el nombre lleva hash y cambiar el archivo cambia la URL. En desarrollo se
sirve como `site.css` con `Last-Modified` pero SIN `Cache-Control`, así que el navegador
aplica caché heurística: guarda el archivo una fracción del tiempo transcurrido desde su
última modificación. Con una hoja editada semanas atrás eso son días, y se siguen viendo
estilos viejos aunque el servidor ya sirva los nuevos. Ocurrió dos veces durante el
cambio de paleta.
"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def _enlace(html):
    import re

    m = re.search(r'href="([^"]*css/site\.css[^"]*)"', html)
    return m.group(1) if m else None


def test_en_desarrollo_la_hoja_lleva_version(settings):
    settings.DEBUG = True
    enlace = _enlace(Client().get("/").content.decode())
    assert enlace is not None, "no se encontró el enlace a la hoja"
    assert "?v=" in enlace, f"sin sufijo de versión: {enlace}"


def test_la_version_cambia_al_editar_la_hoja(settings, tmp_path):
    """Es lo que de verdad importa: que el sufijo siga al archivo, no que exista."""
    import os
    import pathlib

    settings.DEBUG = True
    hoja = pathlib.Path(settings.BASE_DIR) / "static" / "css" / "site.css"
    antes = _enlace(Client().get("/").content.decode())
    original = hoja.stat().st_mtime
    try:
        os.utime(hoja, (original + 120, original + 120))
        despues = _enlace(Client().get("/").content.decode())
    finally:
        os.utime(hoja, (original, original))
    assert antes != despues, f"el sufijo no cambió: {antes}"


def test_fuera_de_desarrollo_no_se_ensucia_la_url(settings):
    """En producción el hash ya hace este trabajo; un ?v= sobrante sería ruido."""
    settings.DEBUG = False
    enlace = _enlace(Client().get("/").content.decode())
    assert enlace is not None
    assert "?v=" not in enlace, f"sufijo innecesario en producción: {enlace}"
