"""El inventario de terceros (NOTICE.md) nombra las fuentes que sirve el sitio, y solo esas.

Las familias autoalojadas son las de las @font-face de site.css que cargan un archivo con url();
las de reserva solo nombran fuentes del sistema con local() y no se distribuyen. Cada familia
autoalojada figura, con su licencia, en una fila de NOTICE.md cuya ubicación es
backend/static/fonts/, y ninguna de esas filas nombra una fuente que el sitio ya no carga: el
inventario no declara una fuente que no se distribuye ni omite una que sí.

Leen NOTICE.md, en la raíz del repositorio: corren en el CI y con el repositorio montado, y se
saltan en el contenedor de desarrollo, que solo monta backend/.
"""

import re
from pathlib import Path

import pytest

from tests import css

NOTICE = Path(__file__).resolve().parents[2] / "NOTICE.md"
FONTS = css.SITE_CSS.parents[1] / "fonts"


def _self_hosted_families():
    """Las familias de las @font-face que cargan un archivo, sin comillas."""
    return {
        face["font-family"].strip("\"'")
        for face in css.at_rules("font-face")
        if "url(" in face.get("src", "")
    }


def _names(component, family):
    """Si la celda nombra la familia entera: «Bricolage Grotesk» no está en «Bricolage Grotesque»."""
    return re.search(rf"(?<![\w-]){re.escape(family)}(?![\w-])", component) is not None


def _font_rows():
    """Las filas de la tabla de NOTICE.md cuya ubicación es backend/static/fonts/, como
    (componente, ubicación, licencia, obligaciones)."""
    if not NOTICE.exists():
        pytest.skip("NOTICE.md vive en la raíz del repositorio, fuera del contenedor")
    rows = []
    for line in NOTICE.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 4 and "backend/static/fonts/" in cells[1]:
            rows.append(tuple(cells))
    return rows


def test_every_self_hosted_font_is_in_the_notice_with_its_license():
    families, rows = _self_hosted_families(), _font_rows()
    # Control: la hoja sirve fuentes propias, y las de reserva (local()) no cuentan como tales.
    assert families and not any(family.endswith("Fallback") for family in families)
    for family in sorted(families):
        named = [row for row in rows if _names(row[0], family)]
        assert named, f"NOTICE.md no inventaría «{family}», que el sitio sirve desde fonts/"
        _, _, license_, duties = named[0]
        assert license_, f"la fila de «{family}» en NOTICE.md no dice su licencia"
        for cited in re.findall(r"`fonts/([^`]+)`", duties):
            assert (FONTS / cited).is_file(), f"NOTICE.md cita fonts/{cited}, que no existe"


def test_the_notice_names_no_font_the_site_no_longer_loads():
    families, rows = _self_hosted_families(), _font_rows()
    stale = [row[0] for row in rows if not any(_names(row[0], family) for family in families)]
    assert not stale, f"NOTICE.md inventaría fuentes que site.css ya no carga: {stale}"
    # Control: se leyeron las filas de fuentes; sin ninguna, la comprobación pasaría en vacío.
    assert rows
