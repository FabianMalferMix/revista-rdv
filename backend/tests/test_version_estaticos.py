"""La hoja de estilos y los guiones propios no se quedan cacheados en desarrollo.

En producción el nombre lleva hash y cambiar el archivo cambia la URL. En desarrollo se
sirven con `Last-Modified` pero SIN `Cache-Control`, así que el navegador aplica caché
heurística: guarda el archivo una fracción del tiempo transcurrido desde su última
modificación. Con una hoja editada semanas atrás eso son días, y se siguen viendo estilos
viejos aunque el servidor ya sirva los nuevos. Ocurrió dos veces durante el cambio de
paleta. Y con los guiones, que no llevaban sufijo: al quitar las flechas de la tirada (D29)
el navegador siguió con el `registros.js` viejo, que fallaba al arrancar, y la pila y el
índice dejaron de responder. El sufijo es la fecha del más reciente de la hoja y los guiones.
"""

import os
import re
from pathlib import Path

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def _enlace(html):
    m = re.search(r'href="([^"]*css/site\.css[^"]*)"', html)
    return m.group(1) if m else None


def _propios(settings):
    raiz = Path(settings.BASE_DIR) / "static"
    return [raiz / "css" / "site.css", *(raiz / "js").glob("*.js")]


def test_en_desarrollo_la_hoja_lleva_version(settings):
    settings.DEBUG = True
    enlace = _enlace(Client().get("/").content.decode())
    assert enlace is not None, "no se encontró el enlace a la hoja"
    assert "?v=" in enlace, f"sin sufijo de versión: {enlace}"


def test_en_desarrollo_cada_guion_propio_lleva_version(settings):
    settings.DEBUG = True
    html = Client().get("/").content.decode()
    sufijos = re.findall(r'<script src="/static/js/[a-z_]+\.js([^"]*)"', html)
    assert sufijos, "no se encontraron guiones propios"
    assert all(re.fullmatch(r"\?v=\d+", s) for s in sufijos), sufijos


def test_la_version_cambia_al_editar_la_hoja(settings):
    """Es lo que de verdad importa: que el sufijo siga al archivo, no que exista. La hoja pasa
    a ser el más reciente de todos, como al guardarla en el editor."""
    settings.DEBUG = True
    hoja = Path(settings.BASE_DIR) / "static" / "css" / "site.css"
    antes = _enlace(Client().get("/").content.decode())
    original = hoja.stat().st_mtime
    nuevo = max(p.stat().st_mtime for p in _propios(settings)) + 120
    try:
        os.utime(hoja, (nuevo, nuevo))
        despues = _enlace(Client().get("/").content.decode())
    finally:
        os.utime(hoja, (original, original))
    assert antes != despues, f"el sufijo no cambió: {antes}"


def test_manda_el_mas_reciente_aunque_sea_un_guion(settings, tmp_path):
    settings.DEBUG = True
    settings.BASE_DIR = tmp_path
    (tmp_path / "static" / "css").mkdir(parents=True)
    (tmp_path / "static" / "js").mkdir()
    hoja = tmp_path / "static" / "css" / "site.css"
    guion = tmp_path / "static" / "js" / "registros.js"
    hoja.write_text("")
    guion.write_text("")
    os.utime(hoja, (1_000, 1_000))
    os.utime(guion, (2_000, 2_000))
    from config.context_processors import version_estaticos

    assert version_estaticos(None) == {"version_estaticos": "?v=2000"}


def test_fuera_de_desarrollo_no_se_ensucia_la_url(settings):
    """En producción el hash ya hace este trabajo; un ?v= sobrante sería ruido."""
    settings.DEBUG = False
    html = Client().get("/").content.decode()
    enlace = _enlace(html)
    assert enlace is not None
    assert "?v=" not in enlace, f"sufijo innecesario en producción: {enlace}"
    assert "?v=" not in "".join(re.findall(r'<script src="([^"]*)"', html))
