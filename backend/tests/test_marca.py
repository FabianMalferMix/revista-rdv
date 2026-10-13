"""La marca del colectivo (backlog UX, ticket 3.7, con lo que eligió el dueño del sitio).

El dueño se quedó con el sello magenta de la cabecera y le añadió el monograma RV dentro;
eligió como icono «RdV» en blanco sobre el mismo magenta, y como tarjeta para compartir el
sello a toda la tarjeta. Antes la pestaña no tenía icono y /favicon.ico daba 404.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.urls import reverse
from PIL import Image

from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db

IMG = Path(settings.BASE_DIR) / "static" / "img"


def _sopa(client):
    return BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")


def test_el_sello_de_la_cabecera_lleva_el_monograma_y_se_llama_como_el_colectivo(client):
    perfil = SiteProfile.load()
    perfil.name = "Repitentes del Verso"
    perfil.save()
    marca = _sopa(client).select_one("a.brand")
    monograma = marca.select_one("svg.brand-mono")
    assert monograma is not None, "el sello perdió su monograma"
    assert monograma["aria-hidden"] == "true", "el monograma es un dibujo: no se anuncia"
    assert [t.get_text() for t in monograma.select("text")] == ["R", "V"]
    assert marca.select_one(".brand-nombre").get_text() == "Repitentes del Verso"


def test_la_pestana_lleva_el_icono_del_colectivo(client):
    cabeza = _sopa(client).head
    iconos = {e["href"].rsplit("/", 1)[-1] for e in cabeza.select('link[rel="icon"]')}
    assert iconos == {"favicon.ico", "icono-32.png"}
    assert cabeza.select_one('link[rel="apple-touch-icon"]')["href"].endswith("icono-180.png")
    assert cabeza.select_one('meta[name="theme-color"]')["content"] == "#d9e8f7"


def test_los_iconos_existen_con_su_tamano():
    """El de la pestaña lleva las esquinas transparentes; el del teléfono es un cuadrado
    entero, porque el teléfono lo redondea y donde hay transparencia el iPhone pone negro."""
    with Image.open(IMG / "icono-32.png") as pestana:
        assert pestana.size == (32, 32) and pestana.mode == "RGBA"
        assert pestana.getpixel((0, 0))[3] == 0, (
            "la esquina del icono de la pestaña no es transparente"
        )
    with Image.open(IMG / "icono-180.png") as telefono:
        assert telefono.size == (180, 180)
        assert telefono.convert("RGBA").getpixel((0, 0))[3] == 255, (
            "el icono del teléfono no puede tener transparencia"
        )
    with Image.open(IMG / "favicon.ico") as ico:
        assert sorted(ico.ico.sizes()) == [(16, 16), (32, 32), (48, 48)]


def test_quien_pide_favicon_ico_recibe_el_icono(client):
    """Lectores de RSS, navegadores viejos y buscadores lo piden en la raíz: daba 404."""
    respuesta = client.get("/favicon.ico")
    assert respuesta.status_code == 302, "temporal: la URL del estático cambia con el icono"
    assert respuesta["Location"].endswith("favicon.ico")
    assert "/static/" in respuesta["Location"] or settings.STATIC_URL in respuesta["Location"]
