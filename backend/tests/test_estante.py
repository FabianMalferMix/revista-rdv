"""El estante de la portada (D24): la opción 3 del tablero «El catálogo en portada», con las
recomendaciones que aceptó el dueño del sitio (2026-10-22).

Una publicación de frente y hasta siete de lomo (cinco en D24; más largo en D25), de pie sobre
la tabla, con la ficha de la de frente al lado y «Ver todo el catálogo →» bajo la tabla. Va de frente la marcada «Featured» y, si no hay, la primera según «Position».
Sin JavaScript cada lomo lleva a su ficha; static/js/estante.js lo convierte en un botón que
saca ese libro al frente. Nada se mueve solo.
"""

from io import BytesIO
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.urls import reverse
from PIL import Image

from apps.content.views import ESTANTE
from apps.media.models import MediaAsset
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


def test_el_lomo_depende_del_tipo(client):
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
    ):
        assert regla in SITE_CSS, regla
    assert (
        "writing-mode:vertical-rl" in SITE_CSS
        and ".es-frente .ejemplar-lomo{display:none}" in SITE_CSS
    )


def _tapa(nombre, borde, centro):
    """Una tapa con un borde de un color y el centro de otro, como las provisionales. En PNG:
    un JPEG corre el color en una unidad y la comparación tiene que ser exacta."""
    imagen = Image.new("RGB", (100, 140), borde)
    imagen.paste(Image.new("RGB", (60, 90), centro), (20, 25))
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    tapa = MediaAsset(alt_text=nombre)
    tapa.file.save(f"{nombre}.png", ContentFile(buffer.getvalue()))
    return tapa


def test_el_lomo_y_el_canto_toman_el_color_de_su_tapa(client):
    """D28: azul de lomo y blanco de frente no era el mismo libro. El lomo lleva el color del
    borde de su tapa y el canto (el grueso que asoma junto a la tapa de frente), uno más
    oscuro; los dos como rectángulos de SVG, porque la CSP no admite estilos en línea. Sobre
    un lomo oscuro, el texto va claro."""
    cache.clear()
    make_publication(slug="rosa", position=0, cover=_tapa("rosa", (246, 214, 230), (20, 30, 200)))
    make_publication(slug="azul", position=1, cover=_tapa("azul", (31, 115, 199), (250, 250, 250)))
    make_publication(slug="sin-tapa", position=2)
    _, estante = _estante(client)
    rosa, azul, sin_tapa = estante.select(".ejemplar")
    assert rosa.select_one(".ejemplar-lomo-fondo rect")["fill"] == "#f6d6e6"
    assert rosa.select_one(".ejemplar-canto rect")["fill"] == "#caafbd"
    assert "ejemplar--oscuro" not in rosa["class"] and "ejemplar--oscuro" in azul["class"]
    assert azul.select_one(".ejemplar-lomo-fondo rect")["fill"] == "#1f73c7"
    assert sin_tapa.select_one("svg") is None
    for svg in estante.select(".ejemplar svg"):
        assert svg["aria-hidden"] == "true" and svg["focusable"] == "false"
    assert ".ejemplar-lomo-fondo{position:absolute; inset:0; z-index:-1;" in SITE_CSS
    assert "nth-child(4n" not in SITE_CSS


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


def test_la_tabla_tiene_aire_al_final_ni_medio_vacia_ni_saturada():
    """D27: la tabla mide lo que sus libros más un tramo libre, proporcional a la pantalla."""
    assert "padding:0 clamp(40px, 6vw, 120px) 0 14px;" in SITE_CSS


def test_el_cambio_de_libro_es_suave():
    """D27: cada libro se desliza desde donde estaba hasta su lugar nuevo (FLIP), el elegido
    gira desde el lomo hasta quedar de frente, y las fichas, apiladas en la misma celda, se
    funden. Un cambio a medias se corta antes del siguiente. Con «reducir movimiento», al
    instante."""
    assert "getBoundingClientRect().left" in ESTANTE_JS and "translateX(${dx}px)" in ESTANTE_JS
    assert "rotateY(-80deg)" in ESTANTE_JS
    assert "seccion.getAnimations({ subtree: true }).forEach((a) => a.cancel())" in ESTANTE_JS
    assert ".estante-fichas{display:grid}" in SITE_CSS
    assert ".estante-ficha{grid-area:1 / 1;" in SITE_CSS


def test_en_pantallas_anchas_los_libros_crecen():
    """D30: a 1900 px el estante y su ficha dejaban unos 360 px vacíos a la derecha; desde
    1400 px los libros crecen (y la tapa pide una copia del tamaño que se ve)."""
    ancho = SITE_CSS[SITE_CSS.index("@media (min-width:1400px){\n  .ejemplar-frente") :]
    assert ".ejemplar-frente{width:270px}" in ancho
    assert ".ejemplar--libro .ejemplar-lomo{width:64px; height:400px}" in ancho
    plantilla = (BACKEND / "templates" / "content" / "home.html").read_text()
    assert "(min-width: 1400px) 270px" in plantilla
