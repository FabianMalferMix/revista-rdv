"""La cabecera de una fila (backlog UX, ticket 4.1; decisiones D2 y D9).

Medía 111 px en escritorio y 156 en el teléfono: el sello y el campo de búsqueda siempre
abierto en una fila, y cuatro enlaces debajo. `/textos/` y el dossier solo estaban en el
pie, y ninguna página decía cuál era la actual. Ahora va en una fila: el sello, cinco
enlaces, una lupa que abre el buscador y el botón «Dossier».
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.reviews.models import Publisher
from tests.factories import make_poem, make_publication, soup

pytestmark = pytest.mark.django_db


def _barra(sopa):
    return {
        a.get_text(): a.get("aria-current", "") for a in sopa.select("header.masthead nav.nav a")
    }


def test_la_barra_marca_la_pagina_actual_y_su_territorio(client):
    """En el índice, «page»; en una página de su territorio, «true»."""
    assert _barra(soup(client, reverse("content:poem_index")))["Poemas"] == "page"
    poema = make_poem(slug="verso", status=EditorialStatus.PUBLISHED, published_at=timezone.now())
    assert _barra(soup(client, poema.get_absolute_url()))["Poemas"] == "true"
    # La agenda está en el territorio del colectivo, que en la barra se llama «Colectivo».
    assert _barra(soup(client, reverse("agenda:agenda")))["Colectivo"] == "true"
    portada = _barra(soup(client, reverse("content:home")))
    assert list(portada) == ["Poemas", "Textos", "Registros", "Publicaciones", "Colectivo"]
    assert not any(portada.values()), "la portada no está en ninguna sección de la barra"


def test_las_fichas_de_una_resena_estan_en_textos(client):
    """A la obra reseñada, su editorial y su autor se llega desde una reseña."""
    editorial = Publisher.objects.create(slug="editorial-x", name="Editorial X")
    # Una editorial tiene ficha cuando publica algo a la vista: sin eso, la dirección da 404.
    make_publication(slug="libro-x", title="Libro X", publisher=editorial)
    barra = _barra(soup(client, reverse("reviews:publisher_detail", args=[editorial.slug])))
    assert barra["Textos"] == "true"


def test_en_el_dossier_lo_marca_su_boton(client):
    """El dossier no está en la barra: lo marca el botón, y solo en el dossier."""
    sopa = soup(client, reverse("showcase:dossier"))
    assert sopa.select_one("header.masthead a.masthead-cta")["aria-current"] == "page"
    nav = _barra(sopa)
    assert "Poemas" in nav, "control: la barra está, con sus enlaces"
    assert not any(nav.values())
    poemas = soup(client, reverse("content:poem_index"))
    assert _barra(poemas)["Poemas"] == "page", "control: en los poemas, la barra marca Poemas"
    assert not poemas.select_one("header.masthead a.masthead-cta").has_attr("aria-current")


def test_el_dossier_esta_a_un_clic_desde_cualquier_pagina(client):
    sopa = soup(client, reverse("agenda:trayectoria"))
    boton = sopa.select_one("header.masthead a.masthead-cta")
    assert boton["href"] == reverse("showcase:dossier") + "#contacto"
    assert boton.find_parent("nav") is None, "el botón va fuera de la barra"
    dossier = soup(client, reverse("showcase:dossier"))
    assert dossier.select_one("#contacto") is not None, "el botón lleva a una sección que no existe"


def test_la_lupa_abre_un_buscador_que_funciona_sin_javascript(client):
    """Un <details> nativo: abre sin JavaScript, y el formulario lleva a /buscar/."""
    busqueda = soup(client, reverse("content:home")).select_one("header.masthead details.busqueda")
    assert busqueda.summary["aria-label"] == "Buscar"
    formulario = busqueda.select_one("form.search")
    assert formulario["action"] == reverse("content:search")
    assert formulario.select_one('input[name="q"]') is not None


def test_el_menu_del_telefono_lleva_el_mapa_del_sitio_sin_encabezados(client):
    """En el menú los rótulos de grupo no son encabezados: irían antes del título de la
    página. En el pie sí lo son."""
    sopa = soup(client, reverse("content:home"))
    menu = sopa.select_one("header.masthead details.nav-disclosure .menu-mapa nav")
    assert menu["aria-label"] == "Menú del sitio"
    assert menu.select("h2") == [], "encabezados en la cabecera, antes del h1 de la página"
    assert [p.get_text() for p in menu.select("p.foot-group-titulo")] == [
        "El colectivo",
        "La obra",
        "Prensa y gestión",
        "Seguir",
    ]
    assert menu.select_one(f'a[href="{reverse("showcase:dossier")}"]') is not None
    pie = sopa.select_one("footer.site-foot nav.foot-groups")
    assert pie["aria-label"] == "Mapa del sitio" and len(pie.select("h2")) == 4


def test_la_subfila_del_colectivo_esta_en_sus_indices(client):
    """D9: «Colectivo» lleva a Integrantes, y desde cada índice del colectivo se llega al
    resto de su territorio."""
    subfila = soup(client, reverse("agenda:agenda")).select_one(".index-head nav.subnav")
    enlaces = {a.get_text(): a.get("aria-current", "") for a in subfila.select("a")}
    assert list(enlaces) == ["Integrantes", "Trayectoria", "Agenda", "Galería", "Prensa", "Aliados"]
    assert enlaces["Agenda"] == "page"
    poem_index = soup(client, reverse("content:poem_index"))
    assert poem_index.select_one(".index-head h1").get_text(strip=True) == "Poemas"  # control
    assert poem_index.select_one(".subnav") is None
