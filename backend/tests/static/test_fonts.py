"""Las fuentes del sitio viajan con él (backend/static/fonts), caben en su presupuesto y llevan
su licencia. La hoja las pide todas, con `font-display: swap`, y ninguna queda huérfana; la de
titulares es Bricolage Grotesque.
"""

import re

import pytest
from django.conf import settings

from tests import css

FUENTES = ["bricolage-grotesque.woff2", "rdv-serif.woff2", "rdv-serif-italic.woff2"]


@pytest.mark.parametrize("archivo", FUENTES)
def test_font_file_is_bundled(archivo):
    font = settings.BASE_DIR / "static" / "fonts" / archivo
    assert font.exists()
    assert font.read_bytes()[:4] == b"wOF2"  # firma woff2 válida


def test_las_fuentes_caben_en_su_presupuesto():
    """La serif de lectura entra si el total de fuentes no pasa de 200 KB (ver «Serif de
    lectura autoalojada» en docs/deferidos-y-decisiones.md). Con los dos ejes completos, la
    serif sola pesaría 302 KB."""
    total = sum((settings.BASE_DIR / "static" / "fonts" / f).stat().st_size for f in FUENTES)
    assert total <= 200 * 1024, f"las fuentes pesan {total / 1024:.0f} KB"


def test_la_licencia_de_la_serif_viaja_con_ella():
    """La OFL exige que cada copia lleve el aviso de copyright y la licencia, y prohíbe que
    una versión modificada use el nombre reservado. Las dos cosas quedan escritas junto a
    los archivos."""
    carpeta = settings.BASE_DIR / "static" / "fonts"
    licencia = (carpeta / "OFL-source-serif-4.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in licencia
    assert "Reserved Font Name" in licencia and "Adobe" in licencia
    aviso = (carpeta / "NOTICE.txt").read_text(encoding="utf-8")
    for clave in (
        "rdv-serif.woff2",
        "rdv-serif-italic.woff2",
        "Source Serif 4",
        "OFL-source-serif-4.txt",
    ):
        assert clave in aviso, f"fonts/NOTICE.txt no menciona «{clave}»"


def _requested_fonts():
    """Cada archivo de fuente que pide una @font-face de la hoja, con su @font-face. La url()
    es relativa: la reescribe WhiteNoise."""
    return {
        archivo: cara
        for cara in css.at_rules("font-face")
        for archivo in re.findall(r'url\("\.\./fonts/([^"]+)"\)', cara.get("src", ""))
    }


def test_css_declares_self_hosted_display_font():
    pedidas = _requested_fonts()
    assert set(FUENTES) <= set(pedidas), sorted(pedidas)
    assert all(cara["font-display"] == "swap" for cara in pedidas.values())
    assert pedidas["bricolage-grotesque.woff2"]["font-family"] == '"Bricolage Grotesque"'
    assert css.split_commas(css.tokens()["--display"])[0] == '"Bricolage Grotesque"'


def test_no_hay_fuentes_huerfanas():
    """Toda fuente empaquetada debe estar referenciada por el CSS.

    Un .woff2 que ya nadie pide no rompe nada visible: simplemente viaja en la
    imagen y en el manifiesto de estáticos. Al cambiar una tipografía, esta prueba
    evita que la anterior quede detrás como archivo muerto.
    """
    fuentes = sorted((settings.BASE_DIR / "static" / "fonts").glob("*.woff2"))
    assert fuentes, "no hay ninguna fuente empaquetada"
    pedidas = _requested_fonts()
    huerfanas = [f.name for f in fuentes if f.name not in pedidas]
    assert not huerfanas, f"fuentes que el CSS no referencia: {huerfanas}"
