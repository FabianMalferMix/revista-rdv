"""Contraste WCAG de la paleta, recalculado desde el propio CSS.

El sitio documenta sus ratios en comentarios. Eso se desincroniza en cuanto
alguien cambia un color: al sustituir la paleta por la de los carteles, el
comentario del sello siguió anunciando 5,12:1 cuando el valor real pasó a ser
6,39:1 —y 5,12 era, además, el contraste de otro par—. Aquí los números no se
leen de los comentarios: se calculan de los colores que el CSS declara de
verdad, así que cambiar un color obliga a seguir cumpliendo AA.
"""

import re

import pytest
from django.conf import settings

# Umbrales de WCAG 2.1 nivel AA para texto (criterio 1.4.3).
AA_NORMAL = 4.5
AA_GRANDE = 3.0


def _canal_lineal(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminancia(hexa):
    h = hexa.lstrip("#")
    if len(h) == 3:  # forma corta #abc
        h = "".join(ch * 2 for ch in h)
    r, g, b = (_canal_lineal(int(h[i : i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(uno, otro):
    a, b = _luminancia(uno), _luminancia(otro)
    claro, oscuro = max(a, b), min(a, b)
    return (claro + 0.05) / (oscuro + 0.05)


def _paleta():
    """Lee las variables de color del bloque :root de site.css."""
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    raiz = re.search(r":root\{(.*?)\n\}", css, re.S)
    assert raiz, "no se encontró el bloque :root"
    colores = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;", raiz.group(1)))
    for nombre in ("paper", "surface", "ink", "muted", "accent", "caratula", "caratula-rotulo"):
        assert nombre in colores, f"la paleta ya no declara --{nombre}"
    return colores


def test_formula_de_contraste_es_correcta():
    """Anclas conocidas: si la fórmula se rompe, lo demás no significa nada."""
    assert contraste("#000000", "#ffffff") == pytest.approx(21, abs=0.01)
    assert contraste("#ffffff", "#ffffff") == pytest.approx(1, abs=0.01)
    assert contraste("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


# Cada par es texto REAL del sitio, no una combinación teórica.
PARES = [
    ("texto principal sobre el papel", "ink", "paper", AA_NORMAL),
    ("texto principal sobre las bandas", "ink", "surface", AA_NORMAL),
    ("texto secundario sobre el papel", "muted", "paper", AA_NORMAL),
    ("texto secundario sobre las bandas", "muted", "surface", AA_NORMAL),
    ("enlace magenta sobre el papel", "accent", "paper", AA_NORMAL),
    ("enlace magenta sobre las bandas", "accent", "surface", AA_NORMAL),
    # La carátula del reproductor lleva el aviso de privacidad en blanco encima,
    # y el botón es blanco sólido. Al azul original del cartel (luminosidad 61%)
    # ese blanco daba 2,90:1; por eso la carátula va hundida a 45%.
    ("aviso en blanco sobre la carátula", "surface", "caratula", AA_NORMAL),
    ("rótulo del botón sobre su fondo blanco", "caratula-rotulo", "surface", AA_NORMAL),
    # Botón primario y bandas de tinta: el papel como texto sobre la tinta.
    ("papel sobre tinta (botón primario, bandas oscuras)", "paper", "ink", AA_NORMAL),
    (
        "blanco sobre el magenta (botón primario al pasar el puntero)",
        "surface",
        "accent",
        AA_NORMAL,
    ),
    ("enlace de salto: papel sobre el magenta", "paper", "accent", AA_NORMAL),
    # El amarillo del cartel entra como SUPERFICIE. Lo que se escribe encima sí debe leerse.
    ("tinta sobre el amarillo del cartel", "ink", "riso-amarillo", AA_NORMAL),
    ("magenta sobre el amarillo del cartel", "accent", "riso-amarillo", AA_NORMAL),
    # Sobre una banda de tinta el acento no puede ser el magenta (2,78:1): es este rosa.
    ("acento sobre una banda de tinta", "accent-on-ink", "ink", AA_NORMAL),
    # El borde de un campo no es texto, pero lo delimita: WCAG 1.4.11 pide 3:1.
    ("borde de un campo sobre el papel", "edge", "paper", AA_GRANDE),
    ("borde de un campo sobre el blanco del campo", "edge", "surface", AA_GRANDE),
    # La hoja clara es el fondo de una fila señalada: todo lo que la fila lleva escrito
    # —título, datos y cejilla— tiene que seguir leyéndose encima.
    ("título sobre la fila señalada", "ink", "paper-2", AA_NORMAL),
    ("datos sobre la fila señalada", "muted", "paper-2", AA_NORMAL),
    ("cejilla sobre la fila señalada", "accent", "paper-2", AA_NORMAL),
]

# Pares que NO se pueden usar como texto sobre fondo. No es una lista de deseos: cada uno
# es una tentación real (dos colores de la paleta que «deberían» combinar) y está aquí con
# su número para que nadie tenga que redescubrirlo.
PROHIBIDOS = [
    ("magenta sobre una banda de tinta", "accent", "ink"),
    ("azul de la carátula como texto sobre el papel", "caratula", "paper"),
    ("texto secundario sobre la carátula", "muted", "caratula"),
    ("amarillo del cartel como texto sobre el papel", "riso-amarillo", "paper"),
    ("acento de las bandas de tinta sobre el papel", "accent-on-ink", "paper"),
]


@pytest.mark.parametrize("descripcion,frente,fondo,minimo", PARES)
def test_contraste_de_la_paleta(descripcion, frente, fondo, minimo):
    colores = _paleta()
    ratio = contraste(colores[frente], colores[fondo])
    assert ratio >= minimo, (
        f"{descripcion}: {colores[frente]} sobre {colores[fondo]} da {ratio:.2f}:1, "
        f"por debajo del mínimo AA de {minimo}:1"
    )


@pytest.mark.parametrize("descripcion,frente,fondo", PROHIBIDOS)
def test_los_pares_prohibidos_siguen_sin_alcanzar_aa(descripcion, frente, fondo):
    """Si un cambio de color hiciera legible uno de estos pares, deja de ser prohibido
    y esta prueba avisa: se mueve a PARES y se permite a propósito."""
    colores = _paleta()
    ratio = contraste(colores[frente], colores[fondo])
    assert ratio < AA_NORMAL, (
        f"{descripcion} da ahora {ratio:.2f}:1 y ya cumple AA: sácalo de PROHIBIDOS"
    )


def _reglas():
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(sel.strip(), cuerpo) for sel, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def _color(valor, colores):
    """Resuelve `var(--x)` o un hexadecimal; None si es otra cosa (rgba, transparent…)."""
    valor = valor.strip()
    variable = re.fullmatch(r"var\(--([a-z0-9-]+)\)", valor)
    if variable:
        return colores.get(variable.group(1))
    return valor if re.fullmatch(r"#[0-9a-fA-F]{3,6}", valor) else None


def test_toda_regla_que_fija_texto_y_fondo_cumple_aa():
    """La tabla de arriba enumera pares; esto comprueba los que el CSS usa DE VERDAD.

    Cualquier regla que declare a la vez `color` y `background` con colores de la paleta
    (o hexadecimales) debe dar 4,5:1. Así un par prohibido no puede colarse en una regla
    nueva aunque nadie lo haya añadido a la tabla.
    """
    colores = _paleta()
    comprobadas, malas = 0, []
    for selector, cuerpo in _reglas():
        frente = re.search(r"(?<![-\w])color:([^;}]+)", cuerpo)
        fondo = re.search(r"background(?:-color)?:([^;}]+)", cuerpo)
        if not frente or not fondo:
            continue
        a, b = _color(frente.group(1), colores), _color(fondo.group(1), colores)
        if not a or not b:
            continue
        comprobadas += 1
        ratio = contraste(a, b)
        if ratio < AA_NORMAL:
            malas.append(f"{selector}: {a} sobre {b} = {ratio:.2f}:1")
    assert comprobadas >= 5, (
        "la prueba dejó de encontrar reglas con texto y fondo: revisar la regex"
    )
    assert not malas, f"reglas con texto y fondo por debajo de AA: {malas}"


# El magenta como color de TEXTO en reposo: solo la receta de la cejilla y el asterisco
# de campo obligatorio. Todo lo demás que se pinta en magenta es un estado.
MAGENTA_EN_REPOSO = {".rotulo--acento, .kicker", ".kicker a", ".form .req"}
ESTADOS = (":hover", ":focus", ":checked", "[aria-current")


def test_el_magenta_no_es_el_color_de_reposo_de_nada_mas():
    """Era «el color de los enlaces»: 27 reglas de texto, nueve piezas en la primera
    pantalla de la portada. Un color que está en todas partes no señala nada."""
    intrusas = [
        selector
        for selector, cuerpo in _reglas()
        if re.search(r"(?<![-\w])color:\s*var\(--accent\)", cuerpo)
        and selector not in MAGENTA_EN_REPOSO
        and not any(estado in selector for estado in ESTADOS)
    ]
    assert not intrusas, f"texto magenta en reposo fuera de la receta: {intrusas}"


def test_los_enlaces_se_reconocen_sin_depender_del_color():
    """Un enlace en tinta necesita su subrayado: es lo único que lo distingue del texto.

    Al pasar los enlaces de magenta a tinta, dos listas que quitaban el subrayado
    (`.work-list a`, `.timeline-items a`) habrían quedado como texto corriente.
    WCAG 1.4.1: el color no puede ser el único medio de señalar algo.

    La trayectoria ya no es una lista de enlaces en línea sino de filas (ticket 2.2): su
    enlace es el TÍTULO de la fila, en la tipografía y el cuerpo de un título, que es lo
    que lo distingue del texto. Solo esas reglas de título pueden quitar el subrayado.
    """
    # La primera regla `a` es la de pantalla; la de impresión, más abajo, la sobrescribe.
    enlace = next(cuerpo for selector, cuerpo in _reglas() if selector == "a")
    reglas = dict(_reglas())
    assert "color:var(--ink)" in enlace and "text-decoration-color:var(--accent)" in enlace
    assert "text-decoration:none" not in reglas.get(".work-list a", ""), (
        "«.work-list a» quedó sin subrayado y en tinta: no se distingue del texto"
    )
    assert ".timeline-items a" not in reglas, "la trayectoria volvió a ser una lista de enlaces"
    # Un enlace sin subrayar solo vale si es un título: su selector debe estar en la regla
    # que da la tipografía de titular.
    titulares = next(sel for sel, cuerpo in _reglas() if "font-family:var(--display)" in cuerpo)
    assert ".fila-titulo" in titulares
    assert "text-decoration:none" in reglas[".fila-titulo a"]


def test_contraste_del_sello_de_la_cabecera():
    """El nombre va en blanco dentro del bloque magenta: el par no está en :root."""
    colores = _paleta()
    ratio = contraste("#ffffff", colores["accent"])
    assert ratio >= AA_NORMAL, (
        f"blanco sobre {colores['accent']} da {ratio:.2f}:1; el sello de la cabecera "
        f"dejaría de cumplir AA"
    )
