"""La cabecera al bajar: la opción C del tablero de la barra, elegida por el dueño el 2026-10-15.

Arriba, la cabecera de siempre sin el filete; en la portada, nada (el nombre grande es la
cabecera, como en brikken.co). Al bajar lo que mide la cabecera, una cápsula centrada. Lo de
arriba lo pinta site.css con `@media (scripting: enabled)` desde el primer cuadro, sin
parpadeo; static/js/cabecera.js solo pone y quita data-barra="pildora". Sin JavaScript queda
la cabecera fija de siempre.
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


CON_JS = _junto(_bloque("@media (scripting: enabled){"))
FUERA = _junto(CSS.replace(_bloque("@media (scripting: enabled){"), ""))


@pytest.mark.django_db
def test_la_cabecera_carga_su_guion_con_defer(client):
    pagina = BeautifulSoup(client.get("/").content, "html.parser")
    guion = pagina.select_one('script[src*="js/cabecera.js"]')
    assert guion is not None and guion.has_attr("defer")


def test_arriba_de_la_portada_no_hay_cabecera_solo_con_javascript():
    """La cápsula escondida y el dossier en el titular, solo con JavaScript: sin él, la
    cabecera de siempre y un solo botón principal por pantalla (paso 19)."""
    escondida = "html:not([data-barra]):has(.hero-nombre).masthead-fila{opacity:0;"
    dossier = "html:has(.hero-nombre).hero-dossier{display:inline-flex}"
    for regla in (escondida, dossier):
        assert regla in CON_JS
        assert regla not in FUERA
    # Escondida no es inalcanzable: aparece al recibir el foco.
    assert (
        "html:not([data-barra]):has(.hero-nombre).masthead-fila:focus-within{opacity:1;" in CON_JS
    )


def test_la_franja_mide_lo_mismo_y_lo_de_abajo_no_se_mueve():
    capsula = ':is(html[data-barra="pildora"],html:not([data-barra]):has(.hero-nombre))'
    assert f"{capsula}.masthead{{height:var(--alto-cabecera);" in CON_JS
    assert (
        "html:not([data-barra]):not(:has(.hero-nombre)).masthead{border-bottom-style:none;min-height:var(--alto-cabecera)}"
        in CON_JS
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
    capsula = ':is(html[data-barra="pildora"],html:not([data-barra]):has(.hero-nombre))'
    franja = f"{capsula}.masthead{{height:var(--alto-cabecera);background:transparent;"
    assert franja in CON_JS and "pointer-events:none}" in CON_JS[CON_JS.index(franja) :]
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
    assert ":root{view-transition-name:none}" in FUERA
    assert "animation-delay:calc(var(--dur-base)-var(--dur-fast))" in FUERA


def test_el_guion_solo_cambia_un_atributo():
    """La CSP no admite estilos en línea: el guion no escribe estilos."""
    assert 'setAttribute("data-barra", "pildora")' in CABECERA_JS
    for prohibido in (".style", "cssText", 'setAttribute("style"'):
        assert prohibido not in CABECERA_JS


def test_enfocar_la_cabecera_no_desplaza_la_pagina():
    """Con el scroll-padding, tabular por la cabecera a mitad de página, o cerrar la lupa con
    Escape, hacía saltar la página unos 450 px."""
    assert (
        ".masthead:is(a,summary,input){scroll-margin-top:calc(-1*(var(--alto-cabecera)+var(--s2)))}"
        in FUERA
    )
    assert "focus({ preventScroll: true })" in BUSCADOR_JS


def test_los_resultados_caben_con_el_zoom_al_400():
    assert "max-height:min(64vh,100dvh-150px)" in _junto(CSS)


def test_en_colores_forzados_se_ve_el_monograma():
    forzados = _junto(_bloque("@media (forced-colors: active){"))
    assert ".brand-mono-r,.brand-mono-v{fill:currentColor}" in forzados
