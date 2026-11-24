"""El buscador de la cabecera, plegado en una lupa (ver «El buscador, plegado en una lupa» y
«El buscador en la barra» en docs/deferidos-y-decisiones.md).

La lupa es un <details> nativo: abre sin JavaScript, y su formulario lleva a /buscar/. Abierta,
el campo ocupa en la misma fila el lugar de los cinco enlaces (vuelven al cerrar); en la cápsula,
la cápsula se vuelve el buscador. Los resultados cuelgan debajo como una tarjeta con el acabado
de la cápsula, caben con el zoom al 400 % y no son una región viva: se anuncia su recuento. Lo
que cambia al buscar cuelga de la lupa abierta (`.busqueda[open]`, o `:has(.busqueda[open])` en
lo que está fuera de ella) y solo toca la cabecera, no la página /buscar/.
"""

import re

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.urls import reverse

from apps.site.views import SEARCH_PANEL
from tests import css
from tests.factories import soup
from tests.repo_root import read

RAIZ = settings.BASE_DIR
BUSCADOR_JS = (RAIZ / "static" / "js" / "buscador.js").read_text()
ABIERTA = ".masthead-fila:has(.busqueda[open])"
LUPA = ".busqueda[open]"
CAPSULA = ':is([data-barra="pildora"], [data-barra="arriba"] > [data-pagina="portada"])'


@pytest.mark.django_db
def test_la_lupa_abre_un_buscador_que_funciona_sin_javascript(client):
    """Un <details> nativo: abre sin JavaScript, y el formulario lleva a /buscar/."""
    busqueda = soup(client, reverse("site:home")).select_one("header.masthead details.busqueda")
    assert busqueda.summary["aria-label"] == "Buscar"
    formulario = busqueda.select_one("form.search")
    assert formulario["action"] == reverse("site:search")
    assert formulario.select_one('input[name="q"]') is not None


def test_al_buscar_el_campo_ocupa_el_lugar_de_los_enlaces():
    assert css.rule((), f"{ABIERTA} .nav-disclosure")["display"] == "none"
    assert css.rule((), LUPA)["flex"] == "1"
    campo = css.rule((), f"{LUPA} .search")
    assert (campo["position"], campo["left"], campo["right"]) == ("absolute", "0", "52px")


def test_la_capsula_conserva_su_ancho_mientras_se_busca():
    """En sus dos estados: al bajar y, abierta desde el teclado, arriba de la portada."""
    capsula = css.rule((), f"{CAPSULA} {ABIERTA}")
    assert capsula["width"] == "min(var(--capsula-ancho), 100% - 24px)"


def test_los_resultados_cuelgan_como_una_tarjeta_de_la_capsula():
    tarjeta = css.rule((), f"{LUPA} .busqueda-resultados:not(:empty)")
    capsula = css.rule((), f"{CAPSULA} .masthead-fila")
    for propiedad in ("background", "border", "border-radius", "box-shadow"):
        assert tarjeta[propiedad] == capsula[propiedad], propiedad


def test_los_resultados_caben_con_el_zoom_al_400():
    assert css.rule((), ".busqueda-resultados")["max-height"] == "min(64vh, 100dvh - 150px)"


def test_buscar_no_desplaza_la_pagina():
    """El campo está en la cabecera fija: enfocarlo, o escribir en él, no desplaza la página.
    Con el margen de arriba, el navegador lo creería tapado y la desplazaría hasta 670 px."""
    assert css.rule((), "html:has(.busqueda[open])")["scroll-padding-top"] == "0"
    assert "campo.focus({ preventScroll: true })" in BUSCADOR_JS


def test_solo_cambia_la_cabecera():
    """Cada regla del buscador en la barra cuelga de la lupa abierta (la de la cabecera, la única
    `.busqueda`), de la fila que la tiene o de <html>, y delante solo puede llevar el estado
    de la cápsula: el formulario de /buscar/, fuera de la cabecera, no cambia."""
    selectores = [s for r in css.rules() for s in r.selectors if ".busqueda[open]" in s]
    assert selectores
    for selector in selectores:
        inicio = selector.removeprefix(f"{CAPSULA} ")
        assert inicio.startswith((LUPA, ABIERTA, "html:has(")), selector


def test_the_search_in_the_header_has_a_single_shape():
    """La búsqueda de la cabecera tiene una sola forma: el campo en la fila y los resultados en
    una tarjeta de la cápsula. Debajo no queda otra para los navegadores sin `:has()` (un panel
    bajo la cabecera, con su borde, su fondo y su sombra, y una tarjeta blanca de resultados):
    la fila tendría que anularla, y quien la retocara no cambiaría nada en ningún navegador de
    hoy. Lo que sitúa el campo o le da acabado a los resultados cuelga de la lupa abierta."""
    reglas = [(selector, regla) for regla in css.rules() for selector in regla.selectors]
    campo = [s for s, _ in reglas if re.search(r"\.busqueda\S* \.search$", s)]
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


def test_the_scripts_find_the_results_by_their_class_like_the_stylesheet():
    """Los guiones del sitio encuentran los resultados por su clase, como la hoja: el id del
    panel es cosa de htmx y de la vista de búsqueda, que lo decide (`SEARCH_PANEL`), y si cambia
    no hay que tocarlos."""
    scripts = {path.name: path.read_text() for path in (RAIZ / "static" / "js").glob("*.js")}
    assert "buscador.js" in scripts, "control: se leyeron los guiones del sitio"
    assert [name for name, text in scripts.items() if SEARCH_PANEL in text] == []


def test_the_browser_smoke_finds_the_results_by_their_class_too():
    """La prueba de humo, que busca con la lupa en un navegador, también."""
    smoke = read("tools/ux/browser-smoke.js")
    assert ".busqueda summary" in smoke, "control: la prueba de humo abre la lupa"
    assert SEARCH_PANEL not in smoke


@pytest.mark.django_db
def test_the_live_search_form_is_only_in_the_lupa_and_only_the_open_lupa_places_it(client):
    """El formulario de la búsqueda en vivo solo está en la lupa de la cabecera, y lo sitúa solo
    la lupa abierta: cerrada, no se pinta. El «…» y los resultados se sitúan contra él, así que
    un formulario fuera de la lupa no tendría contra qué."""
    forms = {}
    for url in (reverse("site:home"), reverse("content:poem_index"), reverse("site:search")):
        soup = BeautifulSoup(client.get(url, {"q": "voz"}).content, "html.parser")
        forms[url] = soup.select(".search")
    assert forms[reverse("site:home")]
    outside = [
        url for url, found in forms.items() for f in found if not f.find_parent(class_="busqueda")
    ]
    assert outside == []
    placing = [
        selector
        for rule in css.rules()
        if "position" in rule
        for selector in rule.selectors
        if re.search(r"(^| )\.search(:[\w-]+(\([^)]*\))?)*$", selector)
    ]
    assert placing and all(selector.startswith(LUPA) for selector in placing), placing


@pytest.mark.django_db
def test_the_search_panel_announces_a_count_and_not_the_whole_list(client):
    """Los resultados no son una región viva: el lector los leería enteros en cada pausa. Se
    anuncia el recuento, en una región de estado aparte que rellena la parcial (test_search)."""
    sopa = BeautifulSoup(client.get(reverse("site:home")).content, "html.parser")
    # Un solo contenedor de resultados.
    resultados = sopa.select(f"#{SEARCH_PANEL}")
    assert len(resultados) == 1
    assert resultados[0].find_parent(attrs={"aria-live": True}) is None
    assert not resultados[0].has_attr("aria-live")
    estado = sopa.select(".busqueda #search-status")
    assert len(estado) == 1 and estado[0]["role"] == "status"
    assert "sr-only" in estado[0]["class"] and estado[0].get_text() == ""
