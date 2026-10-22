"""«El colectivo» en la portada (D22): la opción A, «La plana», que eligió el dueño del sitio
en el tablero «El colectivo en portada» (2026-10-22). Reemplaza a la cinta.

La cabeza a la izquierda, con el botón a /integrantes/; a la derecha, seis retratos con el
nombre impreso encima, y cada retrato lleva a su ficha. El título ya no cuenta: «Las voces».
Con más de seis, los pliegos: todas vienen en la página y «Otras seis» (static/js/
integrantes.js) cambia cuáles se ven. Nada avanza solo. El aspecto está en site.css; aquí,
el reparto, el orden y lo que hace el guion.
"""

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from apps.content.views import PLIEGO_INTEGRANTES
from apps.people.models import Contributor
from tests.factories import make_image

pytestmark = pytest.mark.django_db

BACKEND = Path(__file__).resolve().parent.parent
INTEGRANTES_JS = (BACKEND / "static" / "js" / "integrantes.js").read_text()
SITE_CSS = (BACKEND / "static" / "css" / "site.css").read_text()


def _integrantes(n):
    for i in range(n):
        Contributor.objects.create(
            slug=f"integrante-{i}",
            display_name=f"Integrante {i}",
            role="Poeta",
            is_member=True,
            active=True,
            position=i,
        )


def _seccion(client):
    sopa = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    return sopa, sopa.select_one("section.home-integrantes")


def test_el_titulo_no_cuenta_y_el_boton_lleva_al_colectivo(client):
    """«12 voces» decía el número exacto de integrantes; el dueño prefirió no mostrar cifras
    que delaten el tamaño del colectivo."""
    _integrantes(3)
    _, seccion = _seccion(client)
    assert seccion.select_one(".rotulo").get_text() == "El colectivo"
    assert seccion.select_one("h2").get_text() == "Las voces"
    assert not re.search(r"\d", seccion.select_one(".integrantes-cabeza").get_text())
    assert seccion.select_one(".integrantes-cta a.btn")["href"] == reverse("people:member_index")


def test_cada_retrato_lleva_a_su_ficha_y_el_retrato_no_repite_el_nombre(client):
    """Cada tarjeta es un enlace: al señalarla, solo su retrato pasa a color. El retrato va
    con alt vacío, porque el nombre ya está en el enlace."""
    _integrantes(2)
    con_foto = Contributor.objects.get(slug="integrante-0")
    con_foto.photo = make_image("retrato-0", alt="Retrato de Integrante 0")
    con_foto.save()
    _, seccion = _seccion(client)
    enlaces = seccion.select(".integrantes-pliego > li > a.integrante-enlace")
    assert [a["href"] for a in enlaces] == [
        reverse("people:member_detail", args=[f"integrante-{i}"]) for i in range(2)
    ]
    assert [a.select_one(".member-name").get_text() for a in enlaces] == [
        "Integrante 0",
        "Integrante 1",
    ]
    assert enlaces[0].select_one(".riso-duo img")["alt"] == ""
    # Sin foto, el monograma en la misma caja.
    assert enlaces[1].select_one(".monograma")["aria-hidden"] == "true"
    # Cada retrato, dentro de su propio enlace: ninguno se colorea al señalar otro.
    assert all(d.find_parent("a", class_="integrante-enlace") for d in seccion.select(".riso-duo"))


def test_con_seis_o_menos_no_hay_pliegos(client):
    _integrantes(PLIEGO_INTEGRANTES)
    sopa, seccion = _seccion(client)
    tarjetas = seccion.select(".integrantes-pliego > li")
    assert len(tarjetas) == PLIEGO_INTEGRANTES
    assert not [t for t in tarjetas if t.has_attr("hidden")]
    assert seccion.select_one(".integrantes-mandos") is None
    assert sopa.select_one('script[src*="js/integrantes.js"]') is None


def test_con_mas_de_seis_vienen_todas_y_las_demas_esperan_su_pliego(client):
    """Sin tope: a cada integrante se llega por los pliegos. Sin JavaScript se ven las seis
    primeras, en el orden del panel, y los mandos llegan escondidos: los destapa el guion."""
    _integrantes(20)
    sopa, seccion = _seccion(client)
    tarjetas = seccion.select(".integrantes-pliego > li")
    assert [t.select_one(".member-name").get_text() for t in tarjetas] == [
        f"Integrante {i}" for i in range(20)
    ]
    assert [t.has_attr("hidden") for t in tarjetas] == [False] * PLIEGO_INTEGRANTES + [True] * 14
    mandos = seccion.select_one(".integrantes-mandos")
    assert mandos.has_attr("hidden")
    assert mandos.select_one("[data-anteriores]")["aria-label"] == "Seis anteriores"
    assert mandos.select_one("[data-siguientes]").get_text(strip=True) == "Otras seis→"
    assert seccion.select_one("[data-anuncio]")["aria-live"] == "polite"
    assert sopa.select_one('script[src*="js/integrantes.js"]').has_attr("defer")


def test_la_cinta_ya_no_existe():
    assert not list((BACKEND / "templates").rglob("_member_card_cinta.html"))
    assert "cinta" not in SITE_CSS.replace("reemplaza a la cinta", "")


def test_el_guion_no_avanza_solo_ni_escribe_estilos():
    """Nada avanza solo (ningún temporizador que cambie de pliego), no se toca la dirección ni
    el historial, y la CSP no admite estilos en línea."""
    for prohibido in (
        "setInterval",
        "setTimeout",
        ".style",
        "cssText",
        "location.hash",
        "history.",
    ):
        assert prohibido not in INTEGRANTES_JS
    assert "prefers-reduced-motion: reduce" in INTEGRANTES_JS
    assert "!quieto.matches" in INTEGRANTES_JS and ".animate(" in INTEGRANTES_JS


def test_el_pliego_se_cambia_con_los_mandos_o_con_el_dedo():
    """En el teléfono, deslizar sobre los retratos cambia de pliego (a la izquierda, las
    siguientes), solo con el dedo o el lápiz, y un deslizamiento no abre la ficha de debajo.
    El gesto vertical sigue bajando la página."""
    for evento in ("pointerdown", "pointerup", "pointercancel"):
        assert f"'{evento}'" in INTEGRANTES_JS
    assert "e.pointerType === 'mouse'" in INTEGRANTES_JS
    assert "ir(dx < 0 ? 1 : -1)" in INTEGRANTES_JS
    assert "e.stopPropagation()" in INTEGRANTES_JS
    assert ".home-integrantes.con-js .integrantes-pliego{touch-action:pan-y pinch-zoom}" in SITE_CSS


def test_las_que_se_ven_van_primero_para_que_la_columna_corrida_caiga_en_el_medio():
    """La columna del medio se corre con nth-child, que cuenta también las escondidas: el
    guion pone primero, y en orden, las que se ven."""
    assert "lista.prepend(...visibles)" in INTEGRANTES_JS
    assert ".integrantes-pliego > li:nth-child(3n+2){translate:0 var(--s5)}" in SITE_CSS
