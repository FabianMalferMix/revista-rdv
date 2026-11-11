"""La cabecera de una fila (backlog UX, ticket 4.1; decisiones D2 y D9).

Medía 111 px en escritorio y 156 en el teléfono: el sello y el campo de búsqueda siempre
abierto en una fila, y cuatro enlaces debajo. `/textos/` y el dossier solo estaban en el
pie, y ninguna página decía cuál era la actual. Ahora va en una fila: el sello, cinco
enlaces, una lupa que abre el buscador y el botón «Dossier».
"""

from dataclasses import replace

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.people.models import Contributor
from apps.reviews.models import Publisher
from apps.site import navigation
from tests.factories import make_event, make_poem, make_publication, soup

pytestmark = pytest.mark.django_db


def _barra(sopa):
    return {
        a.get_text(): a.get("aria-current", "") for a in sopa.select("header.masthead nav.nav a")
    }


def _links(nav):
    """Los enlaces de una navegación, en orden: (rótulo, dirección)."""
    return [(a.get_text(strip=True), a["href"]) for a in nav.select("a")]


def _footer_group(page, title):
    """Los enlaces del grupo del mapa del pie que se titula `title`."""
    for group in page.select("footer.site-foot nav.foot-groups div.foot-group"):
        if group.h2.get_text(strip=True) == title:
            return _links(group)
    raise AssertionError(f"el pie no tiene el grupo «{title}»")


def test_la_barra_marca_la_pagina_actual_y_su_territorio(client):
    """En el índice, «page»; en una página de su territorio, «true»."""
    assert _barra(soup(client, reverse("content:poem_index")))["Poemas"] == "page"
    poema = make_poem(slug="verso", status=EditorialStatus.PUBLISHED, published_at=timezone.now())
    assert _barra(soup(client, poema.get_absolute_url()))["Poemas"] == "true"
    # La agenda está en el territorio del colectivo, que en la barra se llama «Colectivo».
    assert _barra(soup(client, reverse("agenda:agenda")))["Colectivo"] == "true"
    portada = _barra(soup(client, reverse("site:home")))
    assert list(portada) == ["Poemas", "Textos", "Registros", "Publicaciones", "Colectivo"]
    assert not any(portada.values()), "la portada no está en ninguna sección de la barra"


def test_a_member_profile_and_an_event_are_in_the_collective(client):
    """El perfil de una integrante y la ficha de una actividad están en «Colectivo», como sus
    índices: la barra lo marca en ellas, y nada más."""
    member = Contributor.objects.create(slug="fernanda", display_name="Fernanda", is_member=True)
    event = make_event(slug="lectura-en-la-plaza", title="Lectura en la plaza")
    for url in (reverse("people:member_detail", args=[member.slug]), event.get_absolute_url()):
        bar = _barra(soup(client, url))
        assert {entry: mark for entry, mark in bar.items() if mark} == {"Colectivo": "true"}, url


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
    busqueda = soup(client, reverse("site:home")).select_one("header.masthead details.busqueda")
    assert busqueda.summary["aria-label"] == "Buscar"
    formulario = busqueda.select_one("form.search")
    assert formulario["action"] == reverse("site:search")
    assert formulario.select_one('input[name="q"]') is not None


def test_el_menu_del_telefono_lleva_el_mapa_del_sitio_sin_encabezados(client):
    """En el menú los rótulos de grupo no son encabezados: irían antes del título de la
    página. En el pie sí lo son."""
    sopa = soup(client, reverse("site:home"))
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


@pytest.mark.parametrize(
    ("view", "label"),
    [
        ("people:member_index", "Integrantes"),
        ("agenda:agenda", "Agenda"),
        ("agenda:trayectoria", "Trayectoria"),
        ("agenda:gallery", "Galería"),
    ],
)
def test_la_subfila_del_colectivo_esta_en_sus_indices(client, view, label):
    """«Colectivo» lleva a Integrantes y está marcado en cada índice del colectivo, y desde cada
    uno se llega al resto de su grupo del mapa, en el orden del mapa."""
    page = soup(client, reverse(view))
    bar = page.select_one("header.masthead nav.nav")
    assert bar.find("a", string="Colectivo")["href"] == reverse("people:member_index")
    assert _barra(page)["Colectivo"] == ("page" if view == "people:member_index" else "true")
    subfila = page.select_one(".index-head nav.subnav")
    assert subfila["aria-label"] == "El colectivo"
    enlaces = {a.get_text(): a.get("aria-current", "") for a in subfila.select("a")}
    assert list(enlaces) == ["Integrantes", "Agenda", "Trayectoria", "Galería"]
    assert {name: mark for name, mark in enlaces.items() if mark} == {label: "page"}
    assert _links(subfila) == _footer_group(page, "El colectivo")
    poem_index = soup(client, reverse("content:poem_index"))
    assert poem_index.select_one(".index-head h1").get_text(strip=True) == "Poemas"  # control
    assert poem_index.select_one(".subnav") is None


@pytest.mark.parametrize(
    ("view", "label"), [("showcase:press_index", "Prensa"), ("showcase:partner_index", "Aliados")]
)
def test_press_and_partners_are_in_press_and_management(client, view, label):
    """Prensa y Aliados están en «Prensa y gestión»: su sub-fila es la de ese grupo del mapa, y
    la barra no marca nada, como en las demás páginas del grupo."""
    page = soup(client, reverse(view))
    subnav = page.select_one(".index-head nav.subnav")
    assert subnav["aria-label"] == "Prensa y gestión"
    marks = {a.get_text(strip=True): a.get("aria-current", "") for a in subnav.select("a")}
    assert list(marks) == ["Dossier", "Prensa", "Aliados", "Enviar una propuesta"]
    assert {name: mark for name, mark in marks.items() if mark} == {label: "page"}
    assert _links(subnav) == _footer_group(page, "Prensa y gestión")
    bar = _barra(page)
    assert list(bar) == ["Poemas", "Textos", "Registros", "Publicaciones", "Colectivo"]  # control
    assert not any(bar.values()), f"la barra marca {bar}"


def _swap_link(monkeypatch, old, new):
    """Pone `new` en lugar de `old` en la estructura de la navegación, en cada sitio donde la
    estructura lo nombra: lo mismo que editar el enlace donde se escribe."""
    groups = {
        id(group): replace(group, links=tuple(new if link is old else link for link in group.links))
        for group in navigation.MAP
    }
    monkeypatch.setattr(navigation, "MAP", tuple(groups[id(group)] for group in navigation.MAP))
    monkeypatch.setattr(
        navigation,
        "BAR",
        tuple(new if entry is old else groups.get(id(entry), entry) for entry in navigation.BAR),
    )


def test_changing_a_link_in_the_navigation_changes_the_bar_the_footer_and_the_phone_menu(
    client, monkeypatch
):
    """La barra, el mapa del pie y el del menú del teléfono salen de la misma estructura: un
    enlace que cambia en ella cambia en los tres, rótulo y dirección."""
    _swap_link(
        monkeypatch,
        navigation.POEMS,
        replace(navigation.POEMS, label="Versos", view="content:collection_index"),
    )
    page = soup(client, reverse("site:home"))
    for where in (
        "header.masthead nav.nav",
        "footer.site-foot nav.foot-groups",
        "header.masthead .menu-mapa nav.foot-groups",
    ):
        links = _links(page.select_one(where))
        assert ("Versos", reverse("content:collection_index")) in links, where
        assert ("Textos", reverse("content:text_archive")) in links, f"control: {where}"
        assert "Poemas" not in dict(links), where


def test_the_bar_and_the_map_put_the_work_in_the_same_order(client):
    """La obra se lee en el mismo orden en el mapa y en la barra, con los registros antes que
    las publicaciones."""
    page = soup(client, reverse("site:home"))
    work = [label for label, _ in _footer_group(page, "La obra")]
    assert work == ["Poemas", "Textos", "Colecciones", "Registros", "Publicaciones"]
    bar = [label for label in _barra(page) if label in work]
    assert bar == ["Poemas", "Textos", "Registros", "Publicaciones"]
    assert bar == [label for label in work if label in bar]
