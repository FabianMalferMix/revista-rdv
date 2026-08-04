"""La navegación principal es visible en escritorio.

La nav vive dentro de un `<details>` que en móvil funciona como desplegable y en
escritorio debe mostrarse en línea. Eso se conseguía forzando `display:flex` sobre el
hijo del `<details>` cerrado — un truco que funcionó durante años y que **Chrome 131
rompió**: desde esa versión el contenido de un `<details>` cerrado vive en el
pseudo-elemento `::details-content` con `content-visibility:hidden`, que gana a
cualquier `display` del hijo.

Resultado: la navegación principal desapareció por completo en escritorio para todos los
usuarios de Chrome. Ninguna prueba lo detectó porque el marcado seguía intacto —la nav
está en el HTML— y el fallo solo existe al pintar.

Este test no puede pintar, así que fija el requisito sobre la hoja de estilos: si alguien
reescribe ese bloque y vuelve a depender solo del `display` del hijo, falla.
"""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "site.css"


def _bloque_escritorio():
    """El contenido del @media de escritorio que gobierna la navegación."""
    texto = CSS.read_text(encoding="utf-8")
    m = re.search(r"@media \(min-width:720px\)\{(.*?)\n\}", texto, re.S)
    assert m, "no se encontró el @media de escritorio en site.css"
    return m.group(1)


def test_la_hoja_de_estilos_existe():
    assert CSS.is_file()


def test_en_escritorio_se_oculta_el_desplegable():
    assert re.search(r"\.nav-disclosure summary\s*\{[^}]*display:\s*none", _bloque_escritorio())


def test_se_abre_el_pseudo_elemento_de_details():
    """Sin esto, Chrome 131+ deja la navegación invisible aunque el hijo tenga display."""
    bloque = _bloque_escritorio()
    assert "::details-content" in bloque, (
        "falta abrir ::details-content: en Chrome 131+ el contenido de un <details> "
        "cerrado queda oculto por content-visibility y la navegación desaparece"
    )
    assert re.search(r"::details-content\s*\{[^}]*content-visibility:\s*visible", bloque)


def test_se_conserva_el_display_para_navegadores_antiguos():
    """La regla de siempre sigue haciendo falta donde ::details-content no existe."""
    assert re.search(r"\.nav-disclosure > \.nav\s*\{[^}]*display:\s*flex", _bloque_escritorio())


def test_en_movil_el_desplegable_sigue_siendo_visible():
    """Fuera del @media, el summary debe verse: es el único acceso a la nav en móvil."""
    texto = CSS.read_text(encoding="utf-8")
    fuera = texto.split("@media (min-width:720px)")[0]
    assert re.search(r"\.nav-disclosure summary\s*\{[^}]*display:\s*inline-flex", fuera)
