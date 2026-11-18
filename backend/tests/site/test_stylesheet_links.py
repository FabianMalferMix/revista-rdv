"""Cada página enlaza las hojas del sitio de la lista, todas y en su orden.

La hoja son varios archivos, uno por capa (`STYLESHEETS`, en config/staticfiles.py), y el orden
de sus `<link>` es el de la lista: lo pinta `{% stylesheet_links %}`, también en la página del
error 500, que no hereda de base.html. En desarrollo cada URL lleva el sufijo que rompe la
caché; la del 500 no, porque se pinta sin contexto.
"""

import re

import pytest
from bs4 import BeautifulSoup
from django.template import loader
from django.templatetags.static import static
from django.urls import reverse

from config.context_processors import version_estaticos
from config.staticfiles import STYLESHEETS

pytestmark = pytest.mark.django_db


def _stylesheets(html):
    """Las URL de las hojas que enlaza la página, en su orden."""
    soup = BeautifulSoup(html, "html.parser")
    return [link["href"] for link in soup.select("link[rel=stylesheet]")]


def test_a_page_links_the_sheets_of_the_list_in_their_order(client):
    response = client.get(reverse("site:home"))
    assert response.status_code == 200
    assert _stylesheets(response.content.decode()) == [static(path) for path in STYLESHEETS]


def test_the_500_page_links_the_same_sheets(client, monkeypatch):
    """Se pide de verdad una página que falla: la respuesta es la que pinta `server_error`."""

    def broken(*args, **kwargs):
        raise RuntimeError("la búsqueda se rompió")

    monkeypatch.setattr("apps.site.views.coincidencias_por_nombre", broken)
    client.raise_request_exception = False
    response = client.get(reverse("site:search"), {"q": "umbral"})
    assert response.status_code == 500
    html = response.content.decode()
    assert "Algo se rompió de nuestro lado" in html
    assert _stylesheets(html) == [static(path) for path in STYLESHEETS]


def test_in_development_every_sheet_carries_the_same_version(client, settings):
    settings.DEBUG = True
    version = version_estaticos(None)["version_estaticos"]
    assert re.fullmatch(r"\?v=\d+", version), version
    links = _stylesheets(client.get(reverse("site:home")).content.decode())
    assert links == [static(path) + version for path in STYLESHEETS]
    # La del 500 se pinta sin contexto, como la pinta `server_error`: sin el sufijo.
    error = loader.get_template("500.html").render()
    assert _stylesheets(error) == [static(path) for path in STYLESHEETS]
