"""La navegación principal es visible en escritorio.

La nav vive dentro de un `<details>`: en el teléfono, su summary («Menú») despliega el mapa
del sitio; en escritorio, el summary se oculta y la nav va en línea. No basta con forzar el
`display` del hijo del `<details>` cerrado: desde Chrome 131, ese contenido vive en el
pseudo-elemento `::details-content` con `content-visibility:hidden`, que gana a cualquier
`display` del hijo, y la navegación no se pintaría. El marcado no cambia: la nav está en el
HTML y el fallo solo se ve al pintar, así que una prueba del marcado no lo detecta.

Estas pruebas no pintan, así que fijan el requisito sobre la hoja de estilos: si el bloque
de escritorio depende solo del `display` del hijo, fallan.
"""

from tests import css

# El bloque de escritorio que gobierna la navegación.
DESKTOP = ("@media (min-width:900px)",)


def test_la_hoja_de_estilos_existe():
    assert css.SITE_SHEETS and all(hoja.is_file() for hoja in css.SITE_SHEETS)


def test_en_escritorio_se_oculta_el_desplegable():
    assert css.rule(DESKTOP, ".nav-disclosure summary")["display"] == "none"


def test_se_abre_el_pseudo_elemento_de_details():
    """En escritorio se abre `::details-content`: sin eso, desde Chrome 131 la navegación no se
    ve aunque el hijo tenga display."""
    assert css.rules_with(DESKTOP, ".nav-disclosure::details-content"), (
        "falta abrir ::details-content: en Chrome 131+ el contenido de un <details> "
        "cerrado queda oculto por content-visibility y la navegación desaparece"
    )
    abierto = css.rule(DESKTOP, ".nav-disclosure::details-content")
    assert abierto["content-visibility"] == "visible"


def test_se_conserva_el_display_para_navegadores_antiguos():
    """En escritorio, el hijo lleva también `display:flex`: es la regla que usan los
    navegadores sin ::details-content."""
    assert css.rule(DESKTOP, ".nav-disclosure > .nav")["display"] == "flex"


def test_on_the_phone_the_menu_summary_is_visible():
    """Fuera del bloque de escritorio, el summary («Menú») se ve: en el teléfono es el único
    camino de la cabecera a las secciones, por el mapa del sitio."""
    assert css.rule((), ".nav-disclosure summary")["display"] == "inline-flex"
