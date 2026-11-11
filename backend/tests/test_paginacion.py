"""Paginación con contador, números y objetivos cómodos (backlog UX, ticket 1.10).

Decía «Página 2 de 4» entre dos enlaces de 12 px. No se sabía cuántas piezas había ni se
podía saltar a una página concreta, y tres plantillas repetían el mismo bloque.
"""

import re

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus, Section, Tag
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from tests.factories import (
    make_article,
    make_poem,
    make_published_article,
    make_published_poem,
    make_recording,
    soup,
)

pytestmark = pytest.mark.django_db


def _poemas(cuantos):
    for i in range(cuantos):
        make_poem(
            slug=f"p{i}",
            title=f"Poema {i}",
            status=EditorialStatus.PUBLISHED,
            published_at=timezone.now(),
        )


def _nav(html):
    return BeautifulSoup(html, "html.parser").select_one("nav.pagination")


def test_una_sola_pagina_no_muestra_paginacion(client):
    _poemas(3)
    page = soup(client, reverse("content:poem_index"))
    assert len(page.select("li.fila--poema")) == 3  # control: la lista está entera
    assert page.select_one("nav.pagination") is None


def test_la_paginacion_cuenta_lo_que_hay(client):
    _poemas(13)
    nav = _nav(client.get(reverse("content:poem_index")).content)
    assert nav is not None
    cuenta = re.sub(r"\s+", " ", nav.select_one(".pagination-count").get_text()).strip()
    assert cuenta == "1–12 de 13 poemas"

    # Una sola pieza en la página: su posición, sin rango.
    nav = _nav(client.get(reverse("content:poem_index") + "?page=2").content)
    cuenta = re.sub(r"\s+", " ", nav.select_one(".pagination-count").get_text()).strip()
    assert cuenta == "13 de 13 poemas"

    make_published_poem(slug="p13")
    nav = _nav(client.get(reverse("content:poem_index") + "?page=2").content)
    cuenta = re.sub(r"\s+", " ", nav.select_one(".pagination-count").get_text()).strip()
    assert cuenta == "13–14 de 14 poemas"


def test_la_pagina_actual_y_los_extremos_se_marcan_sin_depender_del_color(client):
    _poemas(13)
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


def test_con_muchas_paginas_no_se_listan_todas(client):
    """Con veinte páginas se muestran los extremos y el entorno de la actual."""
    _poemas(12 * 20)
    nav = _nav(client.get(reverse("content:poem_index") + "?page=10").content)
    numeros = [a.get_text(strip=True) for a in nav.select(".pagination-pages a[aria-label]")]
    assert numeros == ["1", "9", "10", "11", "20"]
    assert len(nav.select('span[aria-hidden="true"]')) == 2, "faltan las dos elipsis"


def test_los_textos_y_los_registros_usan_la_misma_paginacion(client):
    for i in range(13):
        make_article(slug=f"t{i}", status=EditorialStatus.PUBLISHED, published_at=timezone.now())
    nav = _nav(client.get(reverse("content:text_archive")).content)
    assert "de 13 textos" in nav.get_text()


@pytest.mark.parametrize(
    "owner", ["reviews:work_detail", "reviews:publisher_detail", "reviews:bookauthor_detail"]
)
def test_the_reviews_of_a_work_a_publisher_or_an_author_go_twelve_by_twelve(client, owner):
    """Como los índices: «1–12 de 13 textos», y la última, en la página siguiente."""
    publisher = Publisher.objects.create(slug="editorial", name="Editorial")
    author = BookAuthor.objects.create(slug="autora", name="Autora")
    work = Work.objects.create(slug="obra", title="Obra", publisher=publisher)
    work.authors.add(author)
    for i in range(13):
        make_published_article(slug=f"resena-{i}").reviewed_works.add(work)
    url = {
        "reviews:work_detail": work,
        "reviews:publisher_detail": publisher,
        "reviews:bookauthor_detail": author,
    }[owner].get_absolute_url()

    first = soup(client, url)
    assert len(first.select("li.article-card")) == 12
    nav = first.select_one("nav.pagination")
    count = re.sub(r"\s+", " ", nav.select_one(".pagination-count").get_text()).strip()
    assert count == "1–12 de 13 textos"
    assert nav.find(string=re.compile("Anteriores")).parent.name == "span"
    next_link = nav.find("a", rel="next")
    assert next_link.get_text() == "Siguientes →" and next_link["href"] == "?page=2"

    last = soup(client, url + "?page=2")
    assert len(last.select("li.article-card")) == 1
    nav = last.select_one("nav.pagination")
    count = re.sub(r"\s+", " ", nav.select_one(".pagination-count").get_text()).strip()
    assert count == "13 de 13 textos"
    assert nav.find("a", rel="prev").get_text() == "← Anteriores"


# ── Solo se sirve una página que existe ─────────────────────────────────────


def _thirteen_texts(**fields):
    return [make_published_article(**fields) for _ in range(13)]


def _text_archive():
    _thirteen_texts()
    return reverse("content:text_archive")


def _section_detail():
    section = Section.objects.create(slug="seccion", name="Sección")
    _thirteen_texts(section=section)
    return reverse("content:section_detail", args=[section.slug])


def _tag_detail():
    tag = Tag.objects.create(slug="etiqueta", name="Etiqueta")
    for article in _thirteen_texts():
        article.tags.add(tag)
    return reverse("content:tag_detail", args=[tag.slug])


def _signed_by(is_member):
    person = Contributor.objects.create(slug="firma", display_name="Firma", is_member=is_member)
    for article in _thirteen_texts():
        article.authors.add(person)
    return person.slug


def _contributor_detail():
    return reverse("content:contributor_detail", args=[_signed_by(is_member=False)])


def _member_detail():
    return reverse("people:member_detail", args=[_signed_by(is_member=True)])


def _poem_index():
    _poemas(13)
    return reverse("content:poem_index")


def _recording_index():
    for _ in range(13):
        make_recording()
    return reverse("media:recording_index")


def _reviewed(owner):
    publisher = Publisher.objects.create(slug="editorial", name="Editorial")
    author = BookAuthor.objects.create(slug="autora", name="Autora")
    work = Work.objects.create(slug="obra", title="Obra", publisher=publisher)
    work.authors.add(author)
    for article in _thirteen_texts():
        article.reviewed_works.add(work)
    return {"work": work, "publisher": publisher, "author": author}[owner].get_absolute_url()


# Cada lista que se pagina, con trece piezas: doce en la primera página y una en la segunda.
PAGINATED = {
    "content:text_archive": _text_archive,
    "content:section_detail": _section_detail,
    "content:tag_detail": _tag_detail,
    "content:contributor_detail": _contributor_detail,
    "content:poem_index": _poem_index,
    "people:member_detail": _member_detail,
    "media:recording_index": _recording_index,
    "reviews:work_detail": lambda: _reviewed("work"),
    "reviews:publisher_detail": lambda: _reviewed("publisher"),
    "reviews:bookauthor_detail": lambda: _reviewed("author"),
}


@pytest.mark.parametrize("view", sorted(PAGINATED))
def test_only_a_page_that_exists_is_served(client, view):
    """Un `?page=` que no nombra una página de la lista da 404: el cero, una página de más, el
    número con un cero delante (sería otra dirección de la misma página), lo que no es un
    número y el valor vacío. Control: la segunda página existe, y es la que se sirve."""
    url = PAGINATED[view]()
    current = soup(client, url, data={"page": "2"}).select_one("nav.pagination [aria-current=page]")
    assert current.get_text(strip=True) == "2"
    for value in ("0", "99999", "01", "x", ""):
        assert client.get(url, {"page": value}).status_code == 404, f"?page={value}"


def test_las_tres_listas_comparten_el_parcial():
    """Ninguna plantilla vuelve a escribir su propio bloque de paginación."""
    from django.conf import settings

    plantillas = settings.BASE_DIR / "templates"
    paginated = [
        p for p in plantillas.rglob("*.html") if 'class="pagination"' in p.read_text("utf-8")
    ]
    assert "_pagination.html" in [p.name for p in paginated]  # control: la búsqueda lo ve
    propias = [p.name for p in paginated if p.name != "_pagination.html"]
    assert not propias, f"plantillas con paginación propia: {propias}"
