"""Reglas del sistema visual que solo fallan al pintar.

La suite no tiene navegador. Estas pruebas fijan sobre la hoja de estilos las decisiones
del backlog UX (docs/backlog-ux-ui.md) cuyo incumplimiento no rompe nada salvo lo que se
ve: una cubierta deformada, un título con las líneas sueltas, una columna de lectura de
cien letras. Las cifras en pantalla se miden aparte, con tools/ux.
"""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "site.css"


def _css():
    """La hoja sin comentarios: varios citan llaves y selectores a modo de ejemplo."""
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)


def _reglas():
    """(selector, declaraciones sin espacios) de cada regla, también dentro de @media."""
    return [
        (selector.strip(), re.sub(r"\s+", "", cuerpo))
        for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", _css())
    ]


def _regla(selector):
    encontradas = [cuerpo for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel) == selector]
    assert encontradas, f"no existe la regla «{selector}» en site.css"
    return encontradas[-1]


# ── Imágenes ──────────────────────────────────────────────────────────────


def test_las_imagenes_no_heredan_el_alto_del_atributo_html():
    """`_responsive_img.html` emite width y height para reservar el hueco de la imagen.

    Sin `height:auto` ese alto se aplica literal y gana a `aspect-ratio`: las cubiertas
    se dibujaban a 180×780 y las fotos apaisadas de la galería como tiras verticales.
    Ninguna otra prueba lo veía porque el HTML era correcto.
    """
    cuerpo = _regla("img,video")
    assert "height:auto" in cuerpo, "sin height:auto el alto del atributo HTML se aplica literal"
    assert "max-width:100%" in cuerpo, "una imagen más ancha que su caja desbordaría la página"


def test_toda_imagen_con_proporcion_forzada_deja_el_alto_en_auto():
    """Si una regla fija `aspect-ratio` sobre una imagen, el alto debe quedar libre."""
    sin_auto = [
        selector
        for selector, cuerpo in _reglas()
        if "aspect-ratio" in cuerpo
        and re.search(r"\bimg\b", selector)
        and "height:auto" not in cuerpo
    ]
    assert not sin_auto, f"reglas con aspect-ratio sobre <img> sin height:auto: {sin_auto}"


# ── Tipografía ────────────────────────────────────────────────────────────

# El glifo ▾ del desplegable del menú: es un adorno, no texto que haya que leer.
EXENTOS_DEL_MINIMO = {".nav-disclosure summary::after"}


def test_ningun_texto_baja_de_12px():
    """Nueve reglas pintaban texto a 11px; el mínimo legible del sistema es 12."""
    pequenos = [
        (selector, tam)
        for selector, cuerpo in _reglas()
        if selector not in EXENTOS_DEL_MINIMO
        for tam in re.findall(r"font-size:(\d+(?:\.\d+)?)px", cuerpo)
        if float(tam) < 12
    ]
    assert not pequenos, f"texto por debajo de 12px: {pequenos}"


def test_los_titulos_no_heredan_la_interlinea_de_lectura():
    """El 1.6 del cuerpo es para leer párrafos; en un título separa sus líneas."""
    assert "line-height:1.1" in _regla("h1,h2,h3")


def test_el_cuerpo_de_lectura_tiene_medida():
    """A 18px en 780px el artículo corría a 102 letras por línea; lo legible es 45–75."""
    medida = re.search(r"--medida:\s*(\d+)ch", _css())
    assert medida, "falta el token --medida"
    assert 45 <= int(medida.group(1)) <= 66, "la medida en ch quedó fuera del rango de lectura"
    for selector in (".article.body", ".dek", ".member-about", ".rec-sumario"):
        assert "max-width:var(--medida)" in _regla(selector), f"«{selector}» perdió la medida"


def test_el_poema_no_se_parte_con_guiones():
    """El guionado automático empareja la prosa; en un poema el corte es del autor."""
    con_guiones = [selector for selector, cuerpo in _reglas() if "hyphens:auto" in cuerpo]
    assert con_guiones, "ya no hay guionado en pantallas estrechas"
    assert not [s for s in con_guiones if "poem" in s], "el guionado alcanza a los poemas"


# ── Componentes ───────────────────────────────────────────────────────────


def test_ningun_estado_hover_se_marca_bajando_la_opacidad():
    """Tres botones se atenuaban al pasar el ratón: el texto perdía contraste justo al ir
    a pulsarlo. El estado se marca con color sólido."""
    atenuados = [sel for sel, cuerpo in _reglas() if ":hover" in sel and "opacity:" in cuerpo]
    assert not atenuados, f"estados hover por opacidad: {atenuados}"


def test_todo_boton_comparte_una_receta():
    """Había cinco botones con cinco recetas. El del formulario y el del reproductor
    heredan ahora la de `.btn`; ninguno vuelve a fijar su tipografía por su cuenta."""
    receta = [
        (sel, cuerpo) for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel).startswith(".btn,")
    ]
    assert receta, "desapareció la regla común de los botones"
    selector, cuerpo = receta[0]
    for boton in (".btn", ".form button", ".embed-play"):
        assert boton in selector, f"«{boton}» ya no comparte la receta del botón"
    assert "min-height:44px" in cuerpo, "el botón perdió su alto mínimo de 44 px"
    assert "text-transform:none" in cuerpo, "el botón volvió a las mayúsculas"
    sueltos = [
        sel
        for sel, cuerpo in _reglas()
        if sel != selector
        and re.search(r"\.btn|button|embed-play", sel)
        and "font-family" in cuerpo
    ]
    assert not sueltos, f"botones con tipografía propia: {sueltos}"


# Reglas que pintan texto en mayúsculas. La receta es una; la otra es deuda con fecha: la
# navegación sale de aquí en el ticket 2.3.
MAYUSCULAS_PENDIENTES = {".nav a"}


def test_las_mayusculas_son_una_sola_receta():
    """Quince reglas ponían texto en mayúsculas, con seis espaciados distintos."""
    con_mayusculas = {sel for sel, cuerpo in _reglas() if "text-transform:uppercase" in cuerpo}
    receta = {sel for sel in con_mayusculas if sel.startswith(".rotulo")}
    assert len(receta) == 1, f"debe haber exactamente una receta de rótulo: {receta}"
    extra = con_mayusculas - receta - MAYUSCULAS_PENDIENTES
    assert not extra, f"mayúsculas fuera de la receta de rótulo: {extra}"
    assert "letter-spacing:.1em" in dict(_reglas())[receta.pop()]


def test_el_movimiento_usa_los_tokens_y_respeta_a_quien_pide_menos():
    css = _css()
    for token in ("--r-1:", "--dur-fast:", "--dur-base:", "--ease:", "--edge:"):
        assert token in css, f"falta el token {token}"
    sueltas = [
        (sel, cuerpo)
        for sel, cuerpo in _reglas()
        if "transition:" in cuerpo and "var(--dur-" not in cuerpo
    ]
    assert not sueltas, f"transiciones con duración escrita a mano: {[s for s, _ in sueltas]}"
    menos = re.search(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\n\}", css, re.S)
    assert menos, "falta el bloque global de prefers-reduced-motion"
    assert re.search(r"\*,\s*\*::before,\s*\*::after\{", menos.group(1)), (
        "el bloque debe alcanzar a todo (*), no a una lista de componentes"
    )


def test_los_campos_tienen_un_borde_que_se_ve():
    """El borde de un campo lo delimita: WCAG 1.4.11 pide 3:1. `--border` da 1,17:1."""
    campos = (".search input", ".form input, .form textarea, .form select", ".search-page input")
    for selector in campos:
        cuerpos = [cuerpo for sel, cuerpo in _reglas() if sel == selector]
        assert any("border:1pxsolidvar(--edge)" in c for c in cuerpos), (
            f"«{selector}» sin borde visible"
        )


def test_el_foco_se_ve_sobre_la_placa_del_reproductor():
    """El anillo magenta del sitio da 1,32:1 sobre el azul de la placa."""
    assert "outline-color:#fff" in _regla(".player-consent:focus-visible")


def test_el_panel_de_busqueda_se_cierra_al_dejar_de_usarlo():
    regla = _regla(".search:not(:focus-within):not(:hover)#search-results")
    assert "display:none" in regla


# ── Fuente de titulares ───────────────────────────────────────────────────


def test_syne_tiene_reserva_metrica_y_no_cae_a_la_serif():
    """La reserva era la serif de lectura, un 24 % más estrecha: al cargar Syne el nombre
    del sitio pasaba de 231 a 292 px y todo lo de alrededor saltaba."""
    css = _css()
    pila = re.search(r"--display:([^;]+);", css).group(1)
    assert '"Syne Fallback"' in pila and "var(--serif)" not in pila
    reservas = re.findall(r'@font-face\{[^}]*"Syne Fallback"[^}]*\}', css)
    assert len(reservas) >= 2, "la reserva necesita al menos una cara normal y una negrita"
    for cara in reservas:
        assert "size-adjust:" in cara and "local(" in cara
