"""En desarrollo, la hoja de estilos y los guiones propios llevan `?v=` con la fecha del más
reciente: sin él el navegador seguía con copias viejas (con los guiones, al quitar las flechas de
la tirada, la pila y el índice dejaban de responder). En producción el nombre ya lleva hash."""

import os
import re
from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

ESTATICOS = Path(__file__).resolve().parent.parent / "static"


def test_la_hoja_y_cada_guion_propio_llevan_la_version(client, settings):
    settings.DEBUG = True
    html = client.get(reverse("content:home")).content.decode()
    guiones = re.findall(r'<script src="/static/js/[a-z_]+\.js([^"]*)"', html)
    assert guiones and all(re.fullmatch(r"\?v=\d+", v) for v in guiones), guiones
    assert re.search(r'href="/static/css/site\.css\?v=\d+"', html)


def test_la_version_es_la_del_mas_reciente(client, settings, tmp_path):
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


def test_en_produccion_no_hay_sufijo(settings):
    settings.DEBUG = False
    from config.context_processors import version_estaticos

    assert version_estaticos(None) == {"version_estaticos": ""}
