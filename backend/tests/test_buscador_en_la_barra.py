"""El buscador en la barra: el estilo 4 del tablero del buscador, elegido por el dueño el 2026-10-15.

La lupa abre el campo dentro de la misma fila, en el lugar de los cinco enlaces (vuelven al
cerrar); en la cápsula, la cápsula se vuelve el buscador. Los resultados cuelgan debajo como
una tarjeta con el acabado de la cápsula. Todo cuelga de `:has(.busqueda[open])`: donde no
lo hay, queda el panel de antes; y solo toca la cabecera, no la página /buscar/.
"""

from pathlib import Path

from tests import css

RAIZ = Path(__file__).resolve().parent.parent
BUSCADOR_JS = (RAIZ / "static" / "js" / "buscador.js").read_text()
ABIERTA = ".masthead-fila:has(.busqueda[open])"
CAPSULA = ':is(html[data-barra="pildora"], html[data-barra="arriba"]:has(.hero-nombre))'


def test_al_buscar_el_campo_ocupa_el_lugar_de_los_enlaces():
    assert css.rule((), f"{ABIERTA} .nav-disclosure")["display"] == "none"
    assert css.rule((), f"{ABIERTA} .busqueda")["flex"] == "1"
    campo = css.rule((), f"{ABIERTA} .busqueda .search")
    assert (campo["position"], campo["left"], campo["right"]) == ("absolute", "0", "52px")


def test_la_capsula_conserva_su_ancho_mientras_se_busca():
    capsula = css.rule((), f'html[data-barra="pildora"] {ABIERTA}')
    assert capsula["width"] == "min(var(--capsula-ancho), 100% - 24px)"


def test_los_resultados_cuelgan_como_una_tarjeta_de_la_capsula():
    tarjeta = css.rule((), f"{ABIERTA} .busqueda #search-results:not(:empty)")
    capsula = css.rule((), f"{CAPSULA} .masthead-fila")
    for propiedad in ("background", "border", "border-radius", "box-shadow"):
        assert tarjeta[propiedad] == capsula[propiedad], propiedad


def test_buscar_no_desplaza_la_pagina():
    """El campo está en la cabecera fija: enfocarlo, o escribir en él, desplazaba la página
    hasta 670 px, porque el navegador lo creía tapado por el margen de arriba."""
    assert css.rule((), "html:has(.busqueda[open])")["scroll-padding-top"] == "0"
    assert "campo.focus({ preventScroll: true })" in BUSCADOR_JS


def test_solo_cambia_la_cabecera():
    """Cada regla del estilo nuevo empieza en la fila de la cabecera (o en <html>): el
    formulario de /buscar/, fuera de la cabecera, queda como estaba."""
    selectores = [s for r in css.rules() for s in r.selectors if ":has(.busqueda[open])" in s]
    assert selectores
    for selector in selectores:
        assert selector.startswith((".masthead-fila:has(", "html")), selector
