"""Las hojas de estilos y los guiones propios no se quedan cacheados en desarrollo.

En producción el nombre lleva hash y cambiar el archivo cambia la URL. En desarrollo se
sirven con `Last-Modified` pero SIN `Cache-Control`, así que el navegador aplica caché
heurística: guarda el archivo una fracción del tiempo transcurrido desde su última
modificación. Con una hoja editada semanas atrás eso son días, y se siguen viendo estilos
viejos aunque el servidor ya sirva los nuevos. Ocurrió dos veces durante el cambio de
paleta. Y con los guiones, que no llevaban sufijo: al quitar las flechas de la tirada (D29)
el navegador siguió con el `registros.js` viejo, que fallaba al arrancar, y la pila y el
índice dejaron de responder. El sufijo es la fecha del más reciente de las hojas de la lista
(`STYLESHEETS`) y los guiones, y va en todos.
"""

import os
import re
import shutil
from pathlib import Path

import pytest
from django.test import Client

from config.staticfiles import STYLESHEETS

pytestmark = pytest.mark.django_db


def _enlaces(html):
    """Las URL de las hojas que enlaza la página."""
    return re.findall(r'<link rel="stylesheet" href="([^"]+)">', html)


def _propios(settings):
    raiz = Path(settings.BASE_DIR) / "static"
    return [*(raiz / ruta for ruta in STYLESHEETS), *(raiz / "js").glob("*.js")]


def test_en_desarrollo_cada_hoja_lleva_version(settings):
    settings.DEBUG = True
    enlaces = _enlaces(Client().get("/").content.decode())
    assert len(enlaces) == len(STYLESHEETS), f"no se encontraron los enlaces a las hojas: {enlaces}"
    assert all(re.fullmatch(r"[^?]+\?v=\d+", enlace) for enlace in enlaces), enlaces


def test_en_desarrollo_cada_guion_propio_lleva_version(settings):
    settings.DEBUG = True
    html = Client().get("/").content.decode()
    sufijos = re.findall(r'<script src="/static/js/[a-z_]+\.js([^"]*)"', html)
    assert sufijos, "no se encontraron guiones propios"
    assert all(re.fullmatch(r"\?v=\d+", s) for s in sufijos), sufijos


def _copy_own_statics(settings, tmp_path):
    """Copia las hojas y los guiones propios a `tmp_path`, con sus fechas, y apunta BASE_DIR a la
    copia: la prueba cambia fechas sin tocar los archivos del repositorio."""
    for original in _propios(settings):
        target = tmp_path / original.relative_to(settings.BASE_DIR)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    settings.BASE_DIR = tmp_path


@pytest.mark.parametrize("ruta", STYLESHEETS)
def test_la_version_cambia_al_editar_cualquier_hoja(settings, tmp_path, ruta):
    """Es lo que de verdad importa: que el sufijo siga al archivo, no que exista. La hoja pasa
    a ser el más reciente de todos, como al guardarla en el editor, y cambia la URL de todas:
    la cascada se lee de todas a la vez."""
    settings.DEBUG = True
    _copy_own_statics(settings, tmp_path)
    antes = _enlaces(Client().get("/").content.decode())
    nuevo = max(p.stat().st_mtime for p in _propios(settings)) + 120
    os.utime(tmp_path / "static" / ruta, (nuevo, nuevo))
    despues = _enlaces(Client().get("/").content.decode())
    assert len(despues) == len(STYLESHEETS)
    assert not set(antes) & set(despues), f"el sufijo no cambió: {antes}"
    assert all(enlace.endswith(f"?v={int(nuevo)}") for enlace in despues), despues


def test_manda_el_mas_reciente_aunque_sea_un_guion(settings, tmp_path):
    settings.DEBUG = True
    settings.BASE_DIR = tmp_path
    (tmp_path / "static" / "css").mkdir(parents=True)
    (tmp_path / "static" / "js").mkdir()
    for ruta in STYLESHEETS:
        hoja = tmp_path / "static" / ruta
        hoja.write_text("")
        os.utime(hoja, (1_000, 1_000))
    guion = tmp_path / "static" / "js" / "registros.js"
    guion.write_text("")
    os.utime(guion, (2_000, 2_000))
    from config.context_processors import version_estaticos

    assert version_estaticos(None) == {"version_estaticos": "?v=2000"}


def test_fuera_de_desarrollo_no_se_ensucia_la_url(settings):
    """En producción el hash ya hace este trabajo; un ?v= sobrante sería ruido."""
    settings.DEBUG = False
    html = Client().get("/").content.decode()
    enlaces = _enlaces(html)
    assert len(enlaces) == len(STYLESHEETS), "control: la portada enlaza sus hojas"
    assert "?v=" not in "".join(enlaces), f"sufijo innecesario en producción: {enlaces}"
    scripts = re.findall(r'<script src="([^"]*)"', html)
    assert scripts, "control: la portada pide sus guiones"
    assert "?v=" not in "".join(scripts)
