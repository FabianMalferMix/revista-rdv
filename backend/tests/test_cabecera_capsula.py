"""La cabecera al bajar: la opción C del tablero de la barra, elegida por el dueño el 2026-10-15.

Arriba, la cabecera de siempre sin el filete; en la portada, nada (el nombre grande es la
cabecera, como en brikken.co). Al bajar lo que mide la cabecera, una cápsula centrada.
static/js/cabecera.js se carga en el <head> y pone data-barra="arriba" antes de la primera
pintura, sin parpadeo, y "pildora" al bajar. site.css solo cambia la cabecera con esa marca: sin
JavaScript, o si el guion no llega o falla al montarse, queda la cabecera fija de siempre.
"""

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
CSS = (RAIZ / "static" / "css" / "site.css").read_text()
CABECERA_JS = (RAIZ / "static" / "js" / "cabecera.js").read_text()
BUSCADOR_JS = (RAIZ / "static" / "js" / "buscador.js").read_text()


def _junto(texto):
    return re.sub(r"\s+", "", texto)


def _bloque(cabecera):
    """El texto de un bloque @media, hasta la llave que lo cierra."""
    inicio = CSS.index(cabecera) + len(cabecera)
    nivel = 1
    for i in range(inicio, len(CSS)):
        nivel += {"{": 1, "}": -1}.get(CSS[i], 0)
        if nivel == 0:
            return CSS[inicio:i]
    raise AssertionError(f"el bloque «{cabecera}» no cierra")


HOJA = _junto(CSS)
ARRIBA = 'html[data-barra="arriba"]'
CAPSULA = f':is(html[data-barra="pildora"],{ARRIBA}:has(.hero-nombre))'


@pytest.mark.django_db
def test_the_header_script_runs_in_the_head_before_the_first_paint(client):
    """Sin defer ni async: la marca de la que depende la hoja está antes de pintar el cuerpo."""
    pagina = BeautifulSoup(client.get("/").content, "html.parser")
    guion = pagina.head.select_one('script[src*="js/cabecera.js"]')
    assert guion is not None
    assert not guion.has_attr("defer") and not guion.has_attr("async")


def test_without_the_scripts_mark_no_rule_hides_or_reshapes_the_header():
    """Si cabecera.js no llega o falla, no hay marca, y queda la cabecera fija de siempre: lo
    que la esconde, la vuelve transparente o le quita el puntero exige data-barra."""
    cambian = [
        selector
        for selector, cuerpo in _reglas()
        if re.search(r"\.masthead(-fila)?$", selector)
        and re.search(r"opacity:0|pointer-events:none|background:transparent", cuerpo)
    ]
    assert len(cambian) >= 2
    assert [s for s in cambian if "data-barra" not in s] == []


def test_arriba_de_la_portada_no_hay_cabecera_solo_con_javascript():
    """La cápsula escondida y el dossier en el titular, solo con la marca del guion: sin ella,
    la cabecera de siempre y un solo botón principal por pantalla (paso 19)."""
    escondida = f"{ARRIBA}:has(.hero-nombre).masthead-fila{{opacity:0;"
    dossier = "html[data-barra]:has(.hero-nombre).hero-dossier{display:inline-flex}"
    for regla in (escondida, dossier):
        assert regla in HOJA
    assert [s for s, c in _reglas() if "hero-dossier" in s and "inline-flex" in c] == [
        "html[data-barra]:has(.hero-nombre) .hero-dossier"
    ]
    # Escondida no es inalcanzable: aparece al recibir el foco.
    assert f"{ARRIBA}:has(.hero-nombre).masthead-fila:focus-within{{opacity:1;" in HOJA


def test_la_franja_mide_lo_mismo_y_lo_de_abajo_no_se_mueve():
    assert f"{CAPSULA}.masthead{{height:var(--alto-cabecera);" in HOJA
    assert (
        f"{ARRIBA}:not(:has(.hero-nombre)).masthead{{border-bottom-style:none;min-height:var(--alto-cabecera)}}"
        in HOJA
    )


def _reglas():
    """(selector, declaraciones) de cada regla de la hoja, también dentro de @media, sin
    comentarios y sin espacios."""
    sin_comentarios = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    return [
        (" ".join(selector.split()), _junto(cuerpo))
        for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", sin_comentarios)
    ]


def test_la_franja_no_tapa_lo_que_pasa_junto_a_la_capsula():
    """D34: con la cápsula, la franja de la cabecera es transparente y no recibe el puntero
    en todas las páginas: lo que pasa a su altura se lee y se pulsa a los lados, como en la
    portada. Antes, fuera de la portada, un velo de papel la tapaba de lado a lado y cortaba
    el contenido. Ninguna regla de la cápsula le vuelve a dar fondo a la franja (ni a sus
    pseudoelementos), sea para todas las páginas o para algunas."""
    franja = f"{CAPSULA}.masthead{{height:var(--alto-cabecera);background:transparent;"
    assert franja in HOJA and "pointer-events:none}" in HOJA[HOJA.index(franja) :]
    con_fondo = [
        selector
        for selector, cuerpo in _reglas()
        if 'data-barra="pildora"' in selector
        and re.search(r"\.masthead(::?(before|after))?$", selector)
        and re.search(
            r"(?<![-\w])background(-color|-image)?:(?!transparent[;}]|none[;}])", cuerpo + "}"
        )
    ]
    assert not con_fondo, f"la franja de la cápsula vuelve a tapar el contenido: {con_fondo}"


def test_la_transicion_no_deja_la_cabecera_vacia():
    """La que se va se desvanece después de que la otra empezó a entrar, y la página no
    entra en la transición."""
    assert ":root{view-transition-name:none}" in HOJA
    assert "animation-delay:calc(var(--dur-base)-var(--dur-fast))" in HOJA


def test_el_guion_solo_cambia_un_atributo():
    """La CSP no admite estilos en línea: el guion no escribe estilos."""
    for prohibido in (".style", "cssText", 'setAttribute("style"'):
        assert prohibido not in CABECERA_JS


def test_enfocar_la_cabecera_no_desplaza_la_pagina():
    """Con el scroll-padding, tabular por la cabecera a mitad de página, o cerrar la lupa con
    Escape, hacía saltar la página unos 450 px."""
    assert (
        ".masthead:is(a,summary,input){scroll-margin-top:calc(-1*(var(--alto-cabecera)+var(--s2)))}"
        in HOJA
    )
    assert "focus({ preventScroll: true })" in BUSCADOR_JS


def test_los_resultados_caben_con_el_zoom_al_400():
    assert "max-height:min(64vh,100dvh-150px)" in _junto(CSS)


def test_en_colores_forzados_se_ve_el_monograma():
    forzados = _junto(_bloque("@media (forced-colors: active){"))
    assert ".brand-mono-r,.brand-mono-v{fill:currentColor}" in forzados
