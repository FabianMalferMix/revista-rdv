"""«Las voces» en la portada (D23): la opción 3 del tablero «Las voces en relevo», con la pasada
de tinta de la 2, que eligió el dueño del sitio (2026-10-22). Reemplaza a la cinta y a los
pliegos de D22.

La cabeza a la izquierda, con el botón a /integrantes/; a la derecha, una fila de cinco retratos
(tres en el teléfono) con el nombre debajo, y cada retrato lleva a su ficha. El título no cuenta:
«Las voces». Las demás vienen en la página, escondidas, y el relevo (static/js/integrantes.js)
las trae de a una, cada 1,8 s, bajo una pasada de tinta; en el teléfono, deslizando el dedo.
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from apps.people.models import Contributor
from apps.site.portada import A_LA_VISTA, A_LA_VISTA_TELEFONO
from config.breakpoints import PHONE, below
from tests import css
from tests.factories import make_image, soup
from tests.scripts import taken_from_common

pytestmark = pytest.mark.django_db

BACKEND = Path(__file__).resolve().parent.parent
INTEGRANTES_JS = (BACKEND / "static" / "js" / "integrantes.js").read_text()
NARROW_PHONE = ("@media (max-width:719px)",)


def _integrantes(n):
    for i in range(n):
        Contributor.objects.create(
            slug=f"integrante-{i}",
            display_name=f"Integrante {i}",
            role="Poeta",
            is_member=True,
            active=True,
            position=i,
        )


def _seccion(client):
    sopa = soup(client, reverse("site:home"))
    return sopa, sopa.select_one("section.home-integrantes")


def test_el_titulo_no_cuenta_y_el_boton_lleva_al_colectivo(client):
    """«12 voces» decía el número exacto de integrantes; el dueño prefirió no mostrar cifras
    que delaten el tamaño del colectivo (D22)."""
    _integrantes(3)
    _, seccion = _seccion(client)
    assert seccion.select_one(".rotulo").get_text() == "El colectivo"
    assert seccion.select_one("h2").get_text() == "Las voces"
    assert not re.search(r"\d", seccion.select_one(".integrantes-cabeza").get_text())
    assert seccion.select_one(".integrantes-cta a.btn")["href"] == reverse("people:member_index")


def test_cada_retrato_lleva_a_su_ficha_y_el_retrato_no_repite_el_nombre(client):
    """Cada tarjeta es un enlace: al señalarla, solo su retrato pasa a color. El retrato va
    con alt vacío, porque el nombre ya está en el enlace."""
    _integrantes(2)
    con_foto = Contributor.objects.get(slug="integrante-0")
    con_foto.photo = make_image("retrato-0", alt="Retrato de Integrante 0")
    con_foto.save()
    _, seccion = _seccion(client)
    enlaces = seccion.select(".integrantes-retratos > li > a.integrante-enlace")
    assert [a["href"] for a in enlaces] == [
        reverse("people:member_detail", args=[f"integrante-{i}"]) for i in range(2)
    ]
    assert [a.select_one(".member-name").get_text() for a in enlaces] == [
        "Integrante 0",
        "Integrante 1",
    ]
    assert enlaces[0].select_one(".riso-duo img")["alt"] == ""
    # Sin foto, el monograma en la misma caja.
    assert enlaces[1].select_one(".monograma")["aria-hidden"] == "true"
    # Cada retrato, dentro de su propio enlace: ninguno se colorea al señalar otro.
    assert all(d.find_parent("a", class_="integrante-enlace") for d in seccion.select(".riso-duo"))


def test_con_tres_o_menos_no_hay_relevo(client):
    _integrantes(A_LA_VISTA_TELEFONO)
    sopa, seccion = _seccion(client)
    cards = seccion.select(".integrantes-retratos > li")
    assert len(cards) == A_LA_VISTA_TELEFONO  # control: están todas, a la vista
    assert not [t for t in cards if t.has_attr("hidden")]
    assert sopa.select_one('script[src*="js/integrantes.js"]') is None


def test_vienen_todas_y_las_que_no_caben_esperan_su_turno(client):
    """Sin tope: a cada integrante le llega su turno. Sin JavaScript se ven las cinco primeras,
    en el orden del panel. Sin botones: el relevo es automático, y no se anuncia, porque
    cambiaría cada 1,8 s."""
    _integrantes(20)
    sopa, seccion = _seccion(client)
    tarjetas = seccion.select(".integrantes-retratos > li")
    assert [t.select_one(".member-name").get_text() for t in tarjetas] == [
        f"Integrante {i}" for i in range(20)
    ]
    assert [t.has_attr("hidden") for t in tarjetas] == [False] * A_LA_VISTA + [True] * 15
    assert seccion.select_one("button") is None
    assert seccion.select_one("[aria-live]") is None
    assert sopa.select_one('script[src*="js/integrantes.js"]').has_attr("defer")


def test_five_in_the_row_and_three_on_the_phone(client):
    """Cinco en la fila y tres en el teléfono, decididos solo en Python: la sección los
    lleva en atributos data- para el guion, y sin el guion las que no caben en el teléfono
    van marcadas. Cuántos ve el navegador lo mide la prueba de humo."""
    assert A_LA_VISTA == 5 and A_LA_VISTA_TELEFONO == 3
    _integrantes(8)
    _, seccion = _seccion(client)
    assert seccion["data-a-la-vista"] == str(A_LA_VISTA)
    assert seccion["data-a-la-vista-telefono"] == str(A_LA_VISTA_TELEFONO)
    visibles = [li for li in seccion.select(".integrante") if not li.has_attr("hidden")]
    solo_ancho = ["integrante--solo-ancho" in li["class"] for li in visibles]
    assert solo_ancho == [False] * A_LA_VISTA_TELEFONO + [True] * (A_LA_VISTA - A_LA_VISTA_TELEFONO)


def test_the_script_takes_the_phone_cut_from_the_page(client):
    """Desde qué ancho es el teléfono lo dice la hoja en su corte (`config/breakpoints.py`), y
    la sección se lo pasa al guion: el guion no escribe el suyo."""
    _integrantes(8)
    _, seccion = _seccion(client)
    assert seccion["data-telefono"] == below(PHONE)
    assert css.rules_with((f"@media {below(PHONE)}",), ".integrantes-fila"), "la hoja no corta ahí"
    consultas = re.findall(r"matchMedia\(([^)]*)\)", INTEGRANTES_JS)
    assert any(not c.startswith("'") for c in consultas), "ninguna consulta viene de la página"
    assert not [c for c in consultas if "width" in c], consultas


def test_the_stylesheet_does_not_repeat_how_many_are_shown():
    """La fila tiene una columna por retrato visible: la hoja no fija cuántos son."""
    fila = css.rule((), ".integrantes-retratos")
    assert (fila["grid-auto-flow"], fila["grid-auto-columns"]) == ("column", "minmax(0, 1fr)")
    reglas = [r for r in css.rules() if ".integrantes-retratos" in r.selector]
    assert not [r.selector for r in reglas if any("repeat(" in d.value for d in r.declarations)]
    assert not [r.selector for r in reglas if "nth-child(n+" in r.selector]


def test_the_head_goes_beside_the_portraits_and_above_them_on_the_phone():
    """La cabeza, angosta, a la izquierda de la fila; en el teléfono, encima. Y sin el guion,
    las que la plantilla marca como solo de pantalla ancha se esconden solo en el teléfono."""
    assert css.rule((), ".integrantes-fila")["grid-template-columns"] == (
        "minmax(0, 216px) minmax(0, 1fr)"
    )
    assert css.rule(NARROW_PHONE, ".integrantes-fila")["grid-template-columns"] == "minmax(0, 1fr)"
    solo_ancho = ".home-integrantes:not(.con-js) .integrante--solo-ancho"
    assert css.rule(NARROW_PHONE, solo_ancho)["display"] == "none"
    assert {r.context for r in css.rules() if r.selector == solo_ancho} == {NARROW_PHONE}


def test_el_relevo_corre_solo_con_puntero_y_se_detiene_al_senalar():
    """Como la cinta (D1): solo donde hay un puntero que pueda posarse y no se pidió menos
    movimiento; se detiene con el puntero encima o el foco dentro, fuera de la vista y con la
    pestaña oculta. Así ningún retrato se escapa cuando se va a pulsar."""
    assert "'(hover: hover) and (prefers-reduced-motion: no-preference)'" in INTEGRANTES_JS
    assert "const CADA = 1800;" in INTEGRANTES_JS
    assert "seccion.matches(':hover, :focus-within')" in INTEGRANTES_JS
    assert "document.hidden" in INTEGRANTES_JS and "IntersectionObserver" in INTEGRANTES_JS


def test_llega_bajo_una_pasada_de_tinta():
    """La tinta azul con el filo magenta: una capa que el guion pone y quita; el recorte
    (clipPath) la hace entrar por un lado y salir por el otro."""
    tinta = css.rule((), ".integrante-tinta")
    for propiedad, valor in (
        ("position", "absolute"),
        ("inset", "-4px"),
        ("pointer-events", "none"),
        ("background", "linear-gradient(90deg, var(--caratula) 0 80%, var(--accent) 80% 100%)"),
    ):
        assert tinta.get(propiedad) == valor, propiedad
    assert css.resolve(tinta["z-index"]) == "2"
    # Si se anima lo dice common.js, que responde que no a quien pidió menos movimiento.
    assert "clipPath" in INTEGRANTES_JS and "canAnimate" in taken_from_common(INTEGRANTES_JS)


def test_the_script_only_writes_each_portraits_place_and_leaves_the_address_alone():
    """La CSP bloquea el atributo style (y cssText, que lo escribe entero), no el CSSOM: el guion
    solo le da a cada retrato su lugar en la fila (`order`), porque la lista ya no cambia de
    orden. El aspecto sigue en componentes.css. Que la que llega ocupe el lugar de la que se va, que
    los pares vayan más abajo y que el lector reciba la lista entera lo mira la prueba de humo."""
    assert set(re.findall(r"\.style\b(\.\w+)?", INTEGRANTES_JS)) == {".order"}
    for prohibido in (
        "cssText",
        "setAttribute('style'",
        'setAttribute("style"',
        "setProperty",
        "location.hash",
        "history.",
    ):
        assert prohibido not in INTEGRANTES_JS


def test_en_el_telefono_se_cambia_con_el_dedo():
    """En el teléfono no corre solo: deslizar sobre los retratos trae a otras tres. El gesto lo
    da common.js, como a la tirada; que sea solo del dedo o del lápiz y que un deslizamiento no
    abra la ficha de debajo lo mira la prueba de humo, en el navegador. Deslizar en vertical
    sigue bajando la página."""
    assert "onSwipe" in taken_from_common(INTEGRANTES_JS)
    retratos = css.rule((), ".home-integrantes.con-js .integrantes-retratos")
    assert retratos["touch-action"] == "pan-y pinch-zoom"
