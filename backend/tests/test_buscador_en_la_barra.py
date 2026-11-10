"""El buscador en la barra: el estilo 4 del tablero del buscador, elegido por el dueño el 2026-10-15.

La lupa abre el campo dentro de la misma fila, en el lugar de los cinco enlaces (vuelven al
cerrar); en la cápsula, la cápsula se vuelve el buscador. Los resultados cuelgan debajo como
una tarjeta con el acabado de la cápsula. Todo cuelga de la lupa abierta
(`:has(.busqueda[open])`), y solo toca la cabecera, no la página /buscar/.
"""

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from tests import css

RAIZ = Path(__file__).resolve().parent.parent
BUSCADOR_JS = (RAIZ / "static" / "js" / "buscador.js").read_text()
ABIERTA = ".masthead-fila:has(.busqueda[open])"
CAPSULA = ':is(html[data-barra="pildora"], html[data-barra="arriba"] > [data-pagina="portada"])'


def test_al_buscar_el_campo_ocupa_el_lugar_de_los_enlaces():
    assert css.rule((), f"{ABIERTA} .nav-disclosure")["display"] == "none"
    assert css.rule((), f"{ABIERTA} .busqueda")["flex"] == "1"
    campo = css.rule((), f"{ABIERTA} .busqueda .search")
    assert (campo["position"], campo["left"], campo["right"]) == ("absolute", "0", "52px")


def test_la_capsula_conserva_su_ancho_mientras_se_busca():
    """En sus dos estados: al bajar y, abierta desde el teclado, arriba de la portada."""
    capsula = css.rule((), f"{CAPSULA} {ABIERTA}")
    assert capsula["width"] == "min(var(--capsula-ancho), 100% - 24px)"


def test_los_resultados_cuelgan_como_una_tarjeta_de_la_capsula():
    tarjeta = css.rule((), f"{ABIERTA} .busqueda .busqueda-resultados:not(:empty)")
    capsula = css.rule((), f"{CAPSULA} .masthead-fila")
    for propiedad in ("background", "border", "border-radius", "box-shadow"):
        assert tarjeta[propiedad] == capsula[propiedad], propiedad


def test_buscar_no_desplaza_la_pagina():
    """El campo está en la cabecera fija: enfocarlo, o escribir en él, desplazaba la página
    hasta 670 px, porque el navegador lo creía tapado por el margen de arriba."""
    assert css.rule((), "html:has(.busqueda[open])")["scroll-padding-top"] == "0"
    assert "campo.focus({ preventScroll: true })" in BUSCADOR_JS


def test_solo_cambia_la_cabecera():
    """Cada regla del estilo nuevo cuelga de la lupa abierta en la fila de la cabecera (o en
    <html>), y delante solo puede llevar el estado de la cápsula: el formulario de /buscar/,
    fuera de la cabecera, queda como estaba."""
    selectores = [s for r in css.rules() for s in r.selectors if ":has(.busqueda[open])" in s]
    assert selectores
    for selector in selectores:
        assert selector.removeprefix(f"{CAPSULA} ").startswith((ABIERTA, "html:has(")), selector


def test_the_search_in_the_header_has_a_single_shape():
    """La búsqueda de la cabecera tiene una sola forma: el campo en la fila y los resultados en
    una tarjeta de la cápsula. Debajo no queda otra para los navegadores sin `:has()` (un panel
    bajo la cabecera, con su borde, su fondo y su sombra, y una tarjeta blanca de resultados):
    la fila tendría que anularla, y quien la retocara no cambiaría nada en ningún navegador de
    hoy. Lo que sitúa el campo o le da acabado a los resultados cuelga de la lupa abierta."""
    reglas = [(selector, regla) for regla in css.rules() for selector in regla.selectors]
    campo = [s for s, _ in reglas if s.endswith(".busqueda .search")]
    acabado = {"background", "border", "border-radius", "box-shadow", "padding"}
    tarjeta = [
        s
        for s, regla in reglas
        if ".busqueda-resultados" in s and acabado & {d.name for d in regla.declarations}
    ]
    assert campo and tarjeta, "la prueba dejó de encontrar la búsqueda de la cabecera"
    assert [s for s in campo + tarjeta if ".busqueda[open]" not in s] == []


@pytest.mark.django_db
def test_the_results_are_styled_by_their_class_and_their_id_is_only_htmxs_target(client):
    """La hoja estila los resultados por su clase; el id solo le dice a htmx dónde ponerlos.
    Un id en un selector le gana a cualquier número de clases: quien quisiera cambiar la
    tarjeta tendría que escribir una regla aún más específica. Ningún selector de la hoja
    lleva un id."""
    sopa = BeautifulSoup(client.get(reverse("site:home")).content, "html.parser")
    campo = sopa.select_one('.busqueda input[type="search"]')
    (destino,) = sopa.select(campo["hx-target"])
    assert "busqueda-resultados" in destino["class"]
    selectores = [selector for regla in css.rules() for selector in regla.selectors]
    assert [s for s in selectores if ".busqueda-resultados" in s]
    # Los corchetes van fuera: `[href^="#"]` no es un id.
    con_id = [s for s in selectores if re.search(r"#[\w-]", re.sub(r"\[[^\]]*\]", "", s))]
    assert con_id == []
