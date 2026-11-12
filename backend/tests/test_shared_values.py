"""Un dato, una fuente: lo que comparten la hoja de estilos, las plantillas y los guiones.

Los cortes de la hoja tienen nombre en `config/breakpoints.py`, y de ahí salen los `sizes` de
las imágenes (`{% sizes %}`) y el corte que reciben los guiones; las curvas de las animaciones
están en la hoja, y los guiones las leen. Estas pruebas atan cada copia a su fuente.
"""

import re
from pathlib import Path

import pytest

from apps.media.templatetags.images import SIZES, sizes
from config.breakpoints import (
    CARRIL_WIDE,
    CUTS,
    ESTANTE_WIDE,
    MEASURE,
    PHONE,
    WIDE_FROM_CARRIL,
    below,
    from_cut,
    lane,
)
from tests import css

BACKEND = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((BACKEND / "static" / "js").glob("*.js"))
# Una consulta de ancho escrita a mano: «(max-width: 719px)», «(min-width:1400px)».
HAND_WRITTEN_CUT = re.compile(r"\((?:max|min)-width:\s*\d+px\)")


def _media_queries():
    """Cada consulta @media de la hoja, normalizada, con las que van dentro de otra."""
    contexts = {r.context for r in css.rules()} | {a.context for a in css.at_rules()}
    return {at_rule for context in contexts for at_rule in context if at_rule.startswith("@media")}


@pytest.mark.parametrize("cut", CUTS)
def test_every_named_cut_is_where_the_stylesheet_changes(cut):
    """La hoja cambia en el corte: por debajo con `max-width` de un píxel menos, desde él con
    `min-width`, y ninguna consulta lo cruza por un píxel (719 frente a 720)."""
    queries = " ".join(_media_queries())
    assert f"(max-width:{cut - 1}px)" in queries or f"(min-width:{cut}px)" in queries, (
        f"la hoja no corta en {cut} px: {sorted(_media_queries())}"
    )
    assert f"(max-width:{cut}px)" not in queries and f"(min-width:{cut - 1}px)" not in queries


def test_no_template_module_or_script_writes_a_cut_by_hand():
    """Los cortes se escriben con su nombre: los `sizes`, con `{% sizes %}`; los guiones los
    reciben de la plantilla. Fuera de `config/breakpoints.py`, ninguna plantilla, ningún módulo
    de las apps y ningún guion escribe una consulta de ancho."""
    sources = [
        *(BACKEND / "templates").rglob("*.html"),
        *(BACKEND / "apps").rglob("*.py"),
        *SCRIPTS,
    ]
    assert len(sources) > 100 and SCRIPTS, "no se encontraron las fuentes"
    by_hand = [
        f"{path.relative_to(BACKEND)}: {match.group()}"
        for path in sources
        for match in HAND_WRITTEN_CUT.finditer(path.read_text(encoding="utf-8"))
    ]
    assert not by_hand, by_hand
    # Control: la etiqueta sí escribe el corte, con su nombre.
    assert sizes("placa-pliego").startswith(f"{below(PHONE)} ")
    assert HAND_WRITTEN_CUT.search(sizes("placa-pliego"))


def test_every_sizes_slot_cuts_at_a_named_cut():
    """Los tramos de cada `sizes` empiezan o terminan en un corte con nombre; sin corte, el
    ancho que crece hasta un tope se dice con `min()`."""
    named = {below(c) for c in CUTS} | {from_cut(c) for c in CUTS}
    loose = {
        slot: media
        for slot, (tramos, resto) in SIZES.items()
        for media in [m for m, _ in tramos] + HAND_WRITTEN_CUT.findall(resto)
        if media not in named
    }
    assert not loose, loose
    # Control: hay tramos que mirar, y la etiqueta los une en el orden del registro.
    assert sum(len(tramos) for tramos, _ in SIZES.values()) > len(SIZES) // 2
    assert sizes("tapa-estante").split(", ")[:2] == [
        f"{below(PHONE)} 160px",
        f"{from_cut(ESTANTE_WIDE)} 270px",
    ]


@pytest.mark.parametrize(
    "viewport,wide,content",
    [
        (390, 350, 350),
        (951, 874.92, 780),
        (1280, 1177.6, 780),
        (1500, 1320, 780),
        (1700, 1440, 780),
    ],
)
def test_the_lanes_of_the_sizes_are_the_lanes_of_the_sheet(viewport, wide, content):
    """Casi cada imagen mide una parte de un carril: el ancho (`--wide`, y el de los monitores
    grandes desde CARRIL_WIDE) o el de lectura (`--measure`), o lo que deja la ventana entre los
    dos `--gutter` cuando no cabe. `sizes` no puede leer la hoja y lo repite (`lane()`): a cada
    ancho mide lo mismo que el carril de la hoja, el de `.band-in` y el de `--carriles`."""
    large = viewport >= CARRIL_WIDE
    context = (f"@media {from_cut(CARRIL_WIDE)}",) if large else ()
    reading = re.search(r"\[content-start\]\s*(.+?)\s*\[content-end\]", css.tokens()["--carriles"])
    lanes = {
        "ancho": (
            css.rule((), ".band-in")["width"],
            lane(WIDE_FROM_CARRIL) if large else lane(),
            wide,
        ),
        "lectura": (reading.group(1), lane(MEASURE), content),
    }
    for name, (sheet, copy, measured) in lanes.items():
        # Primero el `--wide` de ese tramo; después, lo que la hoja declara para todos los anchos.
        # Los dos carriles van de borde a borde de la ventana: su 100 % es el de ella.
        resolved = css.resolve(css.resolve(sheet, context)).replace("100%", "100vw")
        assert css.length_at(copy, viewport) == pytest.approx(css.length_at(resolved, viewport)), (
            name
        )
        # Control: lo que mide el carril en Chrome a ese ancho.
        assert css.length_at(resolved, viewport) == pytest.approx(measured), name


def test_an_unknown_sizes_name_is_an_error():
    with pytest.raises(ValueError, match="tapa-de-nada"):
        sizes("tapa-de-nada")


def test_the_scripts_read_their_curves_from_the_stylesheet():
    """Una curva que comparten la hoja y un guion está en la hoja (`--ease`, `--ease-tirada`) y
    el guion la lee con getComputedStyle: ningún guion copia una curva de la hoja, y cada
    propiedad que lee existe."""
    tokens = css.tokens()
    sheet_curves = {re.sub(r"\s", "", v) for v in tokens.values() if v.startswith("cubic-bezier(")}
    read, copied = set(), []
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        read |= {
            (script.name, name) for name in re.findall(r"getPropertyValue\('(--[\w-]+)'\)", text)
        }
        copied += [
            f"{script.name}: {curve}"
            for curve in re.findall(r"cubic-bezier\([^)]*\)", text)
            if re.sub(r"\s", "", curve) in sheet_curves
        ]
    assert not copied, f"curvas de la hoja copiadas en un guion: {copied}"
    # Control: common.js lee la de la tirada, que comparten la tirada y el estante.
    assert ("common.js", "--ease-tirada") in read
    missing = sorted(f"{script}: {name}" for script, name in read if name not in tokens)
    assert not missing, f"los guiones leen propiedades que la hoja no declara: {missing}"
