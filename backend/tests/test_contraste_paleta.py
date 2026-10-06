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
    colores = dict(re.findall(r"--([a-z-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;", raiz.group(1)))
    for nombre in ("paper", "surface", "ink", "muted", "accent"):
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
]


@pytest.mark.parametrize("descripcion,frente,fondo,minimo", PARES)
def test_contraste_de_la_paleta(descripcion, frente, fondo, minimo):
    colores = _paleta()
    ratio = contraste(colores[frente], colores[fondo])
    assert ratio >= minimo, (
        f"{descripcion}: {colores[frente]} sobre {colores[fondo]} da {ratio:.2f}:1, "
        f"por debajo del mínimo AA de {minimo}:1"
    )


def test_contraste_del_sello_de_la_cabecera():
    """El nombre va en blanco dentro del bloque magenta: el par no está en :root."""
    colores = _paleta()
    ratio = contraste("#ffffff", colores["accent"])
    assert ratio >= AA_NORMAL, (
        f"blanco sobre {colores['accent']} da {ratio:.2f}:1; el sello de la cabecera "
        f"dejaría de cumplir AA"
    )
