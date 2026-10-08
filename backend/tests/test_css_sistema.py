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
