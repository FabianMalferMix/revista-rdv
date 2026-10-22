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
from bs4 import BeautifulSoup
from django.urls import reverse

from apps.content.views import A_LA_VISTA, A_LA_VISTA_TELEFONO
from apps.people.models import Contributor
from tests.factories import make_image

pytestmark = pytest.mark.django_db

BACKEND = Path(__file__).resolve().parent.parent
INTEGRANTES_JS = (BACKEND / "static" / "js" / "integrantes.js").read_text()
SITE_CSS = (BACKEND / "static" / "css" / "site.css").read_text()


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
    sopa = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
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
    assert not [t for t in seccion.select(".integrantes-retratos > li") if t.has_attr("hidden")]
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


def test_cinco_en_la_fila_y_tres_en_el_telefono():
    assert A_LA_VISTA == 5 and A_LA_VISTA_TELEFONO == 3
    assert "repeat(5, minmax(0, 1fr))" in SITE_CSS
    telefono = SITE_CSS[SITE_CSS.index("@media (max-width:719px){\n  .integrantes-fila") :]
    assert ".integrantes-retratos > li:nth-child(n+4){display:none}" in telefono
    assert "movil.matches ? 3 : 5" in INTEGRANTES_JS


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
    assert (
        ".integrante-tinta{position:absolute; inset:-4px; z-index:2; pointer-events:none;\n"
        "  background:linear-gradient(90deg, var(--caratula) 0 80%, var(--accent) 80% 100%)}"
    ) in SITE_CSS
    assert "clipPath" in INTEGRANTES_JS and "!quieto.matches" in INTEGRANTES_JS


def test_las_que_se_ven_van_primero_y_la_que_se_va_espera_al_final():
    """Los pares van más abajo con nth-child, que cuenta también las escondidas: la que llega
    ocupa el lugar de la que se va, y esta pasa al final de la espera."""
    assert "viejo.before(nuevo)" in INTEGRANTES_JS and "lista.append(viejo)" in INTEGRANTES_JS
    assert ".integrantes-retratos > li:nth-child(2n){translate:0 var(--s3)}" in SITE_CSS


def test_el_guion_no_escribe_estilos_ni_toca_la_direccion():
    for prohibido in (".style", "cssText", "location.hash", "history."):
        assert prohibido not in INTEGRANTES_JS


def test_en_el_telefono_se_cambia_con_el_dedo():
    """En el teléfono no corre solo: deslizar sobre los retratos trae a otras tres, solo con
    el dedo o el lápiz, y un deslizamiento no abre la ficha de debajo."""
    for evento in ("pointerdown", "pointerup", "pointercancel"):
        assert f"'{evento}'" in INTEGRANTES_JS
    assert "e.pointerType === 'mouse'" in INTEGRANTES_JS
    assert "e.stopPropagation()" in INTEGRANTES_JS
    assert (
        ".home-integrantes.con-js .integrantes-retratos{touch-action:pan-y pinch-zoom}" in SITE_CSS
    )


def test_la_cinta_y_los_pliegos_ya_no_existen():
    assert not list((BACKEND / "templates").rglob("_member_card_cinta.html"))
    assert not list((BACKEND / "templates").rglob("_member_card_plana.html"))
    assert "cinta" not in SITE_CSS.replace("reemplazó a la cinta", "")
    assert "integrantes-pliego" not in SITE_CSS and "data-siguientes" not in INTEGRANTES_JS
