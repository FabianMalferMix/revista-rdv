"""La cabecera al bajar: la opción C del tablero de la barra, elegida por el dueño el 2026-10-15.

Arriba, la cabecera de siempre sin el filete; en la portada, nada (el nombre grande es la
cabecera, como en brikken.co). Al bajar lo que mide la cabecera, una cápsula centrada.
static/js/cabecera.js se carga en el <head> y pone data-barra="arriba" antes de la primera
pintura, sin parpadeo, y "pildora" al bajar. estados.css solo cambia la cabecera con esa marca: sin
JavaScript, o si el guion no llega o falla al montarse, queda la cabecera fija de siempre.
"""

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from tests import css

RAIZ = Path(__file__).resolve().parent.parent
CABECERA_JS = (RAIZ / "static" / "js" / "cabecera.js").read_text()
BUSCADOR_JS = (RAIZ / "static" / "js" / "buscador.js").read_text()

# La marca va en <html>, el único elemento que la lleva: la hoja no lo nombra.
ARRIBA = '[data-barra="arriba"]'
PORTADA = '[data-pagina="portada"]'
CAPSULA = f':is([data-barra="pildora"], {ARRIBA} > {PORTADA})'


@pytest.mark.django_db
def test_the_header_script_runs_in_the_head_before_the_first_paint(client):
    """Sin defer ni async: la marca de la que depende la hoja está antes de pintar el cuerpo."""
    pagina = BeautifulSoup(client.get("/").content, "html.parser")
    guion = pagina.head.select_one('script[src*="js/cabecera.js"]')
    assert guion is not None
    assert not guion.has_attr("defer") and not guion.has_attr("async")


@pytest.mark.django_db
def test_the_portada_is_recognized_by_the_mark_on_its_body(client):
    """La hoja y cabecera.js reconocen la portada por la marca de su <body> (`data-pagina`),
    que decide su plantilla y que llega antes que la cabecera: la hoja la conoce desde la
    primera pintura. La plantilla, la hoja y el guion la nombran igual, y ninguna otra página la
    lleva: la que la llevara se quedaría sin cabecera arriba."""

    def marca(ruta):
        return BeautifulSoup(client.get(ruta).content, "html.parser").body.get("data-pagina")

    portada = marca(reverse("site:home"))
    assert portada
    hoja = {
        nombre
        for regla in css.rules()
        for selector in regla.selectors
        for nombre in re.findall(r'\[data-pagina="([^"]*)"\]', selector)
    }
    guion = set(re.findall(r'dataset\.pagina === "([^"]*)"', CABECERA_JS))
    assert hoja == guion == {portada}, (hoja, guion, portada)
    for ruta in (reverse("site:search"), reverse("agenda:agenda"), "/no-existe/"):
        assert marca(ruta) != portada, ruta


def test_without_the_scripts_mark_no_rule_hides_or_reshapes_the_header():
    """Si cabecera.js no llega o falla, no hay marca, y queda la cabecera fija de siempre: lo
    que la esconde, la vuelve transparente o le quita el puntero exige data-barra."""
    cambian = [
        selector
        for regla in css.rules()
        if regla.get("opacity") == "0"
        or regla.get("pointer-events") == "none"
        or regla.get("background") == "transparent"
        for selector in regla.selectors
        if re.search(r"\.masthead(-fila)?$", selector)
    ]
    assert len(cambian) >= 2
    assert [s for s in cambian if "data-barra" not in s] == []


def test_arriba_de_la_portada_no_hay_cabecera_solo_con_javascript():
    """La cápsula escondida y el dossier en el titular, solo con la marca del guion: sin ella,
    la cabecera de siempre y un solo botón principal por pantalla (paso 19)."""
    assert css.rule((), f"{ARRIBA} > {PORTADA} .masthead-fila")["opacity"] == "0"
    dossier = f"[data-barra] > {PORTADA} .hero-dossier"
    assert css.rule((), dossier)["display"] == "inline-flex"
    assert [
        r.selector
        for r in css.rules()
        if "hero-dossier" in r.selector and r.get("display") == "inline-flex"
    ] == [dossier]
    # Escondida no es inalcanzable: aparece al recibir el foco.
    assert css.rule((), f"{ARRIBA} > {PORTADA} .masthead-fila:focus-within")["opacity"] == "1"


def test_la_franja_mide_lo_mismo_y_lo_de_abajo_no_se_mueve():
    assert css.rule((), f"{CAPSULA} .masthead")["height"] == "var(--alto-cabecera)"
    arriba = css.rule((), f"{ARRIBA} > :not({PORTADA}) .masthead")
    assert arriba["border-bottom-style"] == "none"
    assert arriba["min-height"] == "var(--alto-cabecera)"


def test_la_franja_no_tapa_lo_que_pasa_junto_a_la_capsula():
    """D34: con la cápsula, la franja de la cabecera es transparente y no recibe el puntero
    en todas las páginas: lo que pasa a su altura se lee y se pulsa a los lados, como en la
    portada. Antes, fuera de la portada, un velo de papel la tapaba de lado a lado y cortaba
    el contenido. Ninguna regla de la cápsula le vuelve a dar fondo a la franja (ni a sus
    pseudoelementos), sea para todas las páginas o para algunas."""
    franja = css.rule((), f"{CAPSULA} .masthead")
    assert franja["background"] == "transparent" and franja["pointer-events"] == "none"
    con_fondo = [
        regla.selector
        for regla in css.rules()
        if any(
            'data-barra="pildora"' in s and re.search(r"\.masthead(::?(before|after))?$", s)
            for s in regla.selectors
        )
        and any(
            d.name in ("background", "background-color", "background-image")
            and d.value not in ("transparent", "none")
            for d in regla.declarations
        )
    ]
    assert not con_fondo, f"la franja de la cápsula vuelve a tapar el contenido: {con_fondo}"


def test_la_transicion_no_deja_la_cabecera_vacia():
    """La que se va se desvanece después de que la otra empezó a entrar, y la página no
    entra en la transición."""
    assert css.rule((), ":root")["view-transition-name"] == "none"
    sale = css.rule(
        (), "::view-transition-old(cabecera-abierta), ::view-transition-old(cabecera-capsula)"
    )
    assert sale["animation-delay"] == "calc(var(--dur-base) - var(--dur-fast))"


def test_el_guion_solo_cambia_un_atributo():
    """La CSP no admite estilos en línea: el guion no escribe estilos."""
    for prohibido in (".style", "cssText", 'setAttribute("style"'):
        assert prohibido not in CABECERA_JS


def test_enfocar_la_cabecera_no_desplaza_la_pagina():
    """Con el scroll-padding, tabular por la cabecera a mitad de página, o cerrar la lupa con
    Escape, hacía saltar la página unos 450 px. El margen de los controles de la cabecera
    descuenta exactamente el relleno de la página."""
    relleno = css.rule((), "html")["scroll-padding-top"]
    assert relleno == "calc(var(--alto-cabecera) + var(--s2))"
    margen = css.rule((), ".masthead :is(a, summary, input)")["scroll-margin-top"]
    assert margen == f"calc(-1 * ({relleno.removeprefix('calc(').removesuffix(')')}))"
    assert "focus({ preventScroll: true })" in BUSCADOR_JS


def test_los_resultados_caben_con_el_zoom_al_400():
    assert css.rule((), ".busqueda-resultados")["max-height"] == "min(64vh, 100dvh - 150px)"


def test_en_colores_forzados_se_ve_el_monograma():
    forzados = css.rule(("@media (forced-colors: active)",), ".brand-mono-r, .brand-mono-v")
    assert forzados["fill"] == "currentColor"
