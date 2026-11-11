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

from tests import css

# El bloque de escritorio que gobierna la navegación.
DESKTOP = ("@media (min-width:900px)",)


def test_la_hoja_de_estilos_existe():
    assert css.SITE_SHEETS and all(hoja.is_file() for hoja in css.SITE_SHEETS)


def test_en_escritorio_se_oculta_el_desplegable():
    assert css.rule(DESKTOP, ".nav-disclosure summary")["display"] == "none"


def test_se_abre_el_pseudo_elemento_de_details():
    """Sin esto, Chrome 131+ deja la navegación invisible aunque el hijo tenga display."""
    assert css.rules_with(DESKTOP, ".nav-disclosure::details-content"), (
        "falta abrir ::details-content: en Chrome 131+ el contenido de un <details> "
        "cerrado queda oculto por content-visibility y la navegación desaparece"
    )
    abierto = css.rule(DESKTOP, ".nav-disclosure::details-content")
    assert abierto["content-visibility"] == "visible"


def test_se_conserva_el_display_para_navegadores_antiguos():
    """La regla de siempre sigue haciendo falta donde ::details-content no existe."""
    assert css.rule(DESKTOP, ".nav-disclosure > .nav")["display"] == "flex"


def test_en_movil_el_desplegable_sigue_siendo_visible():
    """Fuera del @media, el summary debe verse: es el único acceso a la nav en móvil."""
    assert css.rule((), ".nav-disclosure summary")["display"] == "inline-flex"
