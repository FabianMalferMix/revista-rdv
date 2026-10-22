"""El estante de la portada (D24): la opción 3 del tablero «El catálogo en portada», con las
recomendaciones que aceptó el dueño del sitio (2026-10-22).

Una publicación de frente y hasta siete de lomo (cinco en D24; más largo en D25), de pie sobre
la tabla, con la ficha de la de frente al lado y «Ver todo el catálogo →» bajo la tabla. Va de frente la marcada «Featured» y, si no hay, la primera según «Position».
Sin JavaScript cada lomo lleva a su ficha; static/js/estante.js lo convierte en un botón que
saca ese libro al frente. Nada se mueve solo.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from apps.content.views import ESTANTE
from apps.reviews.models import Publisher
from tests.factories import make_image, make_publication

pytestmark = pytest.mark.django_db

BACKEND = Path(__file__).resolve().parent.parent
ESTANTE_JS = (BACKEND / "static" / "js" / "estante.js").read_text()
SITE_CSS = (BACKEND / "static" / "css" / "site.css").read_text()


def _estante(client):
    sopa = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    return sopa, sopa.select_one("section.home-publicaciones")


def _titulos(estante):
    return [f.select_one(".estante-titulo").get_text() for f in estante.select(".estante-ficha")]


def test_va_de_frente_la_destacada_y_si_no_la_primera_por_orden(client):
    make_publication(slug="a", title="Primera", position=0)
    make_publication(slug="b", title="Segunda", position=1)
    _, estante = _estante(client)
    assert _titulos(estante) == ["Primera", "Segunda"]
    assert "es-frente" in estante.select(".ejemplar")[0]["class"]
    make_publication(slug="c", title="Destacada", position=2, featured=True)
    _, estante = _estante(client)
    assert _titulos(estante) == ["Destacada", "Primera", "Segunda"]
    assert ["es-frente" in e["class"] for e in estante.select(".ejemplar")] == [True, False, False]
    assert [f.has_attr("hidden") for f in estante.select(".estante-ficha")] == [False, True, True]


def test_hasta_ocho_y_el_catalogo_bajo_la_tabla(client):
    """Más largo desde D25: una de frente y hasta siete de lomo, lo que cabe a 951 px junto a
    la ficha angosta. Quien busca una que no está, tiene «Ver todo el catálogo →» bajo la
    tabla, como botón lleno: en la cabecera era un enlace que pasaba inadvertido."""
    for i in range(10):
        make_publication(slug=f"p{i}", title=f"Publicación {i}", position=i)
    _, estante = _estante(client)
    assert ESTANTE == 8
    assert len(estante.select(".estante-tabla > .ejemplar")) == ESTANTE
    catalogo = estante.select_one(".estante-mueble > .estante-catalogo a.btn.btn--primary")
    assert catalogo["href"] == reverse("showcase:publication_index")
    assert catalogo.get_text(strip=True) == "Ver todo el catálogo→"
    assert estante.select_one(".estante-cabeza a") is None
    # La tabla mide lo que sus libros, sin tramos vacíos, y la ficha ocupa el resto (D26).
    assert ".estante{display:grid; grid-template-columns:auto minmax(0, 1fr);" in SITE_CSS
    assert "width:fit-content; max-width:100%; border-bottom:5px solid var(--ink)" in SITE_CSS


def test_sin_guion_el_lomo_lleva_a_la_ficha_y_la_tapa_no_repite_el_enlace(client):
    pub = make_publication(slug="cuadernos", title="Cuadernos del ruido", year=2024)
    pub.cover = make_image("tapa", alt="Tapa de Cuadernos del ruido")
    pub.save()
    make_publication(slug="otra", title="Otra", position=1)
    _, estante = _estante(client)
    ficha = reverse("showcase:publication_detail", args=["cuadernos"])
    lomo = estante.select(".ejemplar")[0].select_one("a.ejemplar-lomo")
    assert lomo["href"] == ficha
    assert lomo.get_text(" ", strip=True) == "Cuadernos del ruido 2024"
    tapa = estante.select_one(".es-frente a.ejemplar-frente")
    assert tapa["href"] == ficha and tapa["tabindex"] == "-1" and tapa["aria-hidden"] == "true"
    assert tapa.select_one("img")["alt"] == ""


def test_la_ficha_dice_tipo_anio_editorial_y_sinopsis(client):
    make_publication(
        slug="cuadernos",
        title="Cuadernos del ruido",
        kind="libro",
        year=2024,
        publisher=Publisher.objects.create(name="Overol"),
        synopsis="Primer libro individual de Fernanda Soto.",
    )
    _, estante = _estante(client)
    ficha = estante.select_one(".estante-ficha")
    assert ficha.select_one(".estante-dato").get_text() == "Libro · 2024 · Overol"
    assert ficha.select_one(".estante-titulo")["tabindex"] == "-1"
    assert ficha.select_one(".estante-sinopsis").get_text() == (
        "Primer libro individual de Fernanda Soto."
    )
    boton = ficha.select_one("a.btn")
    assert boton.get_text(strip=True) == "Ver la publicación→"
    assert boton["href"] == reverse("showcase:publication_detail", args=["cuadernos"])


def test_el_lomo_depende_del_tipo_y_lleva_las_tintas_del_sitio(client):
    make_publication(slug="a", kind="libro", position=0)
    make_publication(slug="b", kind="plaquette", position=1)
    make_publication(slug="c", kind="fanzine", position=2)
    _, estante = _estante(client)
    clases = [e["class"] for e in estante.select(".ejemplar")]
    assert ["ejemplar--libro" in clases[0], "ejemplar--plaquette" in clases[1]] == [True, True]
    assert "ejemplar--fanzine" in clases[2]
    for regla in (
        ".ejemplar--libro .ejemplar-lomo{width:50px; height:300px}",
        ".ejemplar--plaquette .ejemplar-lomo{width:28px; height:246px}",
        ".ejemplar--fanzine .ejemplar-lomo{width:36px; height:268px}",
        ".estante-tabla > li:nth-child(4n+1) .ejemplar-lomo{background:var(--caratula)",
        ".estante-tabla > li:nth-child(4n+2) .ejemplar-lomo{background:var(--accent)",
        ".estante-tabla > li:nth-child(4n+3) .ejemplar-lomo{background:var(--riso-amarillo)",
        ".estante-tabla > li:nth-child(4n+4) .ejemplar-lomo{background:var(--surface)",
    ):
        assert regla in SITE_CSS, regla
    assert (
        "writing-mode:vertical-rl" in SITE_CSS
        and ".es-frente .ejemplar-lomo{display:none}" in SITE_CSS
    )


def test_con_una_sola_no_hay_guion(client):
    make_publication(slug="unica")
    sopa, _ = _estante(client)
    assert sopa.select_one('script[src*="js/estante.js"]') is None
    make_publication(slug="segunda", position=1)
    sopa, _ = _estante(client)
    assert sopa.select_one('script[src*="js/estante.js"]').has_attr("defer")


def test_el_guion_saca_al_frente_sin_moverse_solo():
    """El lomo pasa a ser un botón («Sacar al frente» antes del título que se ve), el foco va
    al título de la ficha nueva, y nada avanza solo ni escribe estilos en línea."""
    for prohibido in (
        "setInterval",
        "setTimeout",
        ".style",
        "cssText",
        "location.hash",
        "history.",
    ):
        assert prohibido not in ESTANTE_JS
    assert "enlace.replaceWith(boton)" in ESTANTE_JS and "'Sacar al frente: '" in ESTANTE_JS
    assert "querySelector('.estante-titulo').focus({ preventScroll: true })" in ESTANTE_JS
    assert "prefers-reduced-motion: reduce" in ESTANTE_JS and "!quieto.matches" in ESTANTE_JS
