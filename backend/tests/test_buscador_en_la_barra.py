"""El buscador en la barra: el estilo 4 del tablero del buscador, elegido por el dueño el 2026-10-15.

La lupa abre el campo dentro de la misma fila, en el lugar de los cinco enlaces (vuelven al
cerrar); en la cápsula, la cápsula se vuelve el buscador. Los resultados cuelgan debajo como
una tarjeta con el acabado de la cápsula. Todo cuelga de `:has(.busqueda[open])`: donde no
lo hay, queda el panel de antes; y solo toca la cabecera, no la página /buscar/.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSS = (RAIZ / "static" / "css" / "site.css").read_text()
BUSCADOR_JS = (RAIZ / "static" / "js" / "buscador.js").read_text()
JUNTO = re.sub(r"\s+", "", CSS)
ABIERTA = ".masthead-fila:has(.busqueda[open])"


def test_al_buscar_el_campo_ocupa_el_lugar_de_los_enlaces():
    assert f"{ABIERTA}.nav-disclosure{{display:none}}" in JUNTO
    assert f"{ABIERTA}.busqueda{{flex:1;" in JUNTO
    assert f"{ABIERTA}.busqueda.search{{position:absolute;left:0;right:52px;" in JUNTO


def test_la_capsula_conserva_su_ancho_mientras_se_busca():
    assert (
        f'html[data-barra="pildora"]{ABIERTA}{{width:min(var(--capsula-ancho),100%-24px)}}' in JUNTO
    )


def test_los_resultados_cuelgan_como_una_tarjeta_de_la_capsula():
    regla = f"{ABIERTA}.busqueda#search-results:not(:empty){{"
    assert regla in JUNTO
    assert "box-shadow:6px6px0var(--line)" in JUNTO.split(regla, 1)[1].split("}", 1)[0]


def test_buscar_no_desplaza_la_pagina():
    """El campo está en la cabecera fija: enfocarlo, o escribir en él, desplazaba la página
    hasta 670 px, porque el navegador lo creía tapado por el margen de arriba."""
    assert "html:has(.busqueda[open]){scroll-padding-top:0}" in JUNTO
    assert "campo.focus({ preventScroll: true })" in BUSCADOR_JS


def test_solo_cambia_la_cabecera():
    """Cada regla del estilo nuevo empieza en la fila de la cabecera (o en <html>): el
    formulario de /buscar/, fuera de la cabecera, queda como estaba."""
    sin_comentarios = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    selectores = [
        s for s in re.findall(r"([^{}]+)\{", sin_comentarios) if ":has(.busqueda[open])" in s
    ]
    assert selectores
    for lista in selectores:
        for selector in lista.split(","):
            selector = selector.strip()
            assert selector.startswith((".masthead-fila:has(", "html")), selector
