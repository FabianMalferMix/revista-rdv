"""Paginación con contador, números y objetivos cómodos (backlog UX, ticket 1.10).

Decía «Página 2 de 4» entre dos enlaces de 12 px. No se sabía cuántas piezas había ni se
podía saltar a una página concreta, y tres plantillas repetían el mismo bloque.
"""

import re

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus

pytestmark = pytest.mark.django_db


def _poemas(make_poem, cuantos):
    for i in range(cuantos):
        make_poem(
            slug=f"p{i}",
            title=f"Poema {i}",
            status=EditorialStatus.PUBLISHED,
            published_at=timezone.now(),
        )


def _nav(html):
    return BeautifulSoup(html, "html.parser").select_one("nav.pagination")


def test_una_sola_pagina_no_muestra_paginacion(client, make_poem):
    _poemas(make_poem, 3)
    assert _nav(client.get(reverse("content:poem_index")).content) is None


def test_la_paginacion_cuenta_lo_que_hay(client, make_poem):
    _poemas(make_poem, 13)
    nav = _nav(client.get(reverse("content:poem_index")).content)
    assert nav is not None
    cuenta = re.sub(r"\s+", " ", nav.select_one(".pagination-count").get_text()).strip()
    assert cuenta == "1–12 de 13 poemas"

    nav = _nav(client.get(reverse("content:poem_index") + "?page=2").content)
    cuenta = re.sub(r"\s+", " ", nav.select_one(".pagination-count").get_text()).strip()
    assert cuenta == "13–13 de 13 poemas"


def test_la_pagina_actual_y_los_extremos_se_marcan_sin_depender_del_color(client, make_poem):
    _poemas(make_poem, 13)
    nav = _nav(client.get(reverse("content:poem_index")).content)

    actual = nav.select("[aria-current=page]")
    assert [a.get_text(strip=True) for a in actual] == ["1"]
    # En la primera página «Anteriores» no lleva a ningún sitio: no es un enlace.
    anterior = nav.find(string=re.compile("Anteriores")).parent
    assert anterior.name == "span" and anterior.get("aria-disabled") == "true"
    siguiente = nav.find("a", rel="next")
    assert siguiente and siguiente["href"] == "?page=2"

    nav = _nav(client.get(reverse("content:poem_index") + "?page=2").content)
    assert nav.find("a", rel="prev")["href"] == "?page=1"
    assert nav.find(string=re.compile("Siguientes")).parent.name == "span"


def test_con_muchas_paginas_no_se_listan_todas(client, make_poem):
    """Con veinte páginas se muestran los extremos y el entorno de la actual."""
    _poemas(make_poem, 12 * 20)
    nav = _nav(client.get(reverse("content:poem_index") + "?page=10").content)
    numeros = [a.get_text(strip=True) for a in nav.select(".pagination-pages a[aria-label]")]
    assert numeros == ["1", "9", "10", "11", "20"]
    assert len(nav.select('span[aria-hidden="true"]')) == 2, "faltan las dos elipsis"


def test_los_textos_y_los_registros_usan_la_misma_paginacion(client, make_article):
    for i in range(13):
        make_article(slug=f"t{i}", status=EditorialStatus.PUBLISHED, published_at=timezone.now())
    nav = _nav(client.get(reverse("content:text_archive")).content)
    assert "de 13 textos" in nav.get_text()


def test_las_tres_listas_comparten_el_parcial():
    """Ninguna plantilla vuelve a escribir su propio bloque de paginación."""
    from django.conf import settings

    plantillas = settings.BASE_DIR / "templates"
    propias = [
        p.name
        for p in plantillas.rglob("*.html")
        if p.name != "_pagination.html" and 'class="pagination"' in p.read_text("utf-8")
    ]
    assert not propias, f"plantillas con paginación propia: {propias}"
