"""Las firmas salen en el orden de la coautoría, no en el del alfabeto.

Cada caso firma a «Zoe Zamora» antes que a «Ana Abarca»: el alfabeto las pondría al revés,
así que cada aserción de orden es también el control de que las dos firmas aparecen.
"""

import json
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.content.models import ArticleContributor, EditorialStatus, Poem, PoemContributor
from apps.people.models import Contributor

pytestmark = pytest.mark.django_db

ORDEN = ["Zoe Zamora", "Ana Abarca"]


def _sopa(client, url):
    respuesta = client.get(url)
    assert respuesta.status_code == 200
    return BeautifulSoup(respuesta.content, "html.parser")


def _firmantes():
    return [
        Contributor.objects.create(slug="zoe", display_name="Zoe Zamora"),
        Contributor.objects.create(slug="ana", display_name="Ana Abarca"),
    ]


@pytest.fixture
def texto(make_article):
    zoe, ana = _firmantes()
    articulo = make_article(
        slug="a-cuatro-manos",
        title="A cuatro manos",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    # Ana entra primero en la tabla: el orden lo decide `position`, no el alta.
    ArticleContributor.objects.create(article=articulo, contributor=ana, position=1)
    ArticleContributor.objects.create(article=articulo, contributor=zoe, position=0)
    return articulo


@pytest.fixture
def poema():
    zoe, ana = _firmantes()
    pieza = Poem.objects.create(
        slug="a-dos-voces",
        title="A dos voces",
        body="Un verso",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    PoemContributor.objects.create(poem=pieza, contributor=ana, position=1)
    PoemContributor.objects.create(poem=pieza, contributor=zoe, position=0)
    return pieza


def _mas_de(sopa):
    return [
        li.a.get_text()
        for li in sopa.select("nav.pie-entidad li")
        if li.select_one(".rotulo").get_text() == "Más de"
    ]


def test_article_page_signs_in_coauthorship_order(client, texto):
    sopa = _sopa(client, texto.get_absolute_url())
    assert [a.get_text() for a in sopa.select(".lectura-firmas a")] == ORDEN
    assert [m["content"] for m in sopa.select('meta[property="article:author"]')] == ORDEN


def test_article_footer_offers_more_from_each_author_in_order(client, texto):
    assert _mas_de(_sopa(client, texto.get_absolute_url())) == ORDEN


def test_article_json_ld_lists_authors_in_order(client, texto):
    sopa = _sopa(client, texto.get_absolute_url())
    datos = [json.loads(s.string) for s in sopa.select('script[type="application/ld+json"]')]
    articulo = next(d for d in datos if d.get("@type") != "Organization" and "author" in d)
    assert [a["name"] for a in articulo["author"]] == ORDEN


def test_article_card_signs_in_order(client, texto):
    sopa = _sopa(client, reverse("content:text_archive"))
    fila = next(f for f in sopa.select("li.fila") if "A cuatro manos" in f.get_text())
    assert [a.get_text() for a in fila.select(".fila-pie a")] == ORDEN


def test_rss_names_authors_in_order(client, texto):
    respuesta = client.get(reverse("feed"))
    assert respuesta.status_code == 200
    item = ElementTree.fromstring(respuesta.content).find("channel/item")
    assert item.findtext("title") == "A cuatro manos"
    assert item.findtext("{http://purl.org/dc/elements/1.1/}creator") == ", ".join(ORDEN)


def test_poem_page_and_card_sign_in_order(client, poema):
    sopa = _sopa(client, poema.get_absolute_url())
    assert [a.get_text() for a in sopa.select(".lectura-firmas a")] == ORDEN
    assert _mas_de(sopa) == ORDEN
    indice = _sopa(client, reverse("content:poem_index"))
    fila = next(f for f in indice.select("li.fila") if "A dos voces" in f.get_text())
    assert [a.get_text() for a in fila.select(".fila-pie a")] == ORDEN


def test_same_position_keeps_the_order_they_were_added(client, make_article):
    """El inline del panel crea todas las filas en la posición 0: desempata el alta."""
    zoe, ana = _firmantes()
    articulo = make_article(
        slug="empate", status=EditorialStatus.PUBLISHED, published_at=timezone.now()
    )
    ArticleContributor.objects.create(article=articulo, contributor=zoe)
    ArticleContributor.objects.create(article=articulo, contributor=ana)
    sopa = _sopa(client, articulo.get_absolute_url())
    assert [a.get_text() for a in sopa.select(".lectura-firmas a")] == ORDEN
