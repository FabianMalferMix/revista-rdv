"""Índices como filas tipográficas (backlog UX, ticket 2.2).

Textos, poemas, trayectoria y prensa eran tarjetas apiladas con todo pegado a la
izquierda: en el carril ancho dejaban dos tercios de la pantalla vacíos. Ahora son filas
con un dato a cada lado del título, y la fila entera es el enlace. Lo que solo se ve al
pintar (anchos, estados) se comprueba aparte, sobre la hoja de estilos y con tools/ux.
"""

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Milestone
from apps.content.models import (
    ArticleContributor,
    Collection,
    CollectionPoem,
    EditorialStatus,
    PoemContributor,
    PublishStatus,
    Section,
)
from apps.content.templatetags.versos import primer_verso, primeros_versos
from apps.people.models import Contributor
from apps.showcase.models import PressMention
from tests.factories import make_event, make_publication

pytestmark = pytest.mark.django_db


def _publicado(fabrica, **kw):
    return fabrica(status=EditorialStatus.PUBLISHED, published_at=timezone.now(), **kw)


def _sopa(client, nombre, *args):
    return BeautifulSoup(client.get(reverse(nombre, args=args)).content, "html.parser")


# ── El primer verso ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cuerpo,cuantos,esperado",
    [
        (
            "Verso uno\n    verso con sangría\n\nVerso final",
            3,
            ["Verso uno", "verso con sangría", "Verso final"],
        ),
        ("\n\n   \nPrimero\nSegundo", 1, ["Primero"]),
        ("uno\ndos\ntres\ncuatro", 2, ["uno", "dos"]),
        ("a   b\tc", 1, ["a b c"]),
        ("solo uno", 3, ["solo uno"]),
        ("", 2, []),
        ("   \n\n", 2, []),
        (None, 2, []),
    ],
)
def test_primeros_versos(cuerpo, cuantos, esperado):
    """Un verso es una línea con texto: las líneas en blanco no cuentan y la sangría,
    que en la ficha se respeta, en una cita de índice se descarta."""
    assert primeros_versos(cuerpo, cuantos) == esperado


def test_primer_verso():
    assert primer_verso("\n   Llueve sobre el patio  \nsegundo") == "Llueve sobre el patio"
    assert primer_verso("") == ""
    assert primer_verso(None) == ""


def test_la_fila_del_poema_cita_su_primer_verso(client, make_poem):
    """Es lo que permite reconocer un poema sin abrirlo, como en el índice de primeros
    versos de una antología. Antes la tarjeta enseñaba solo título, autoría y fecha."""
    _publicado(make_poem, slug="patio", body="\n   Llueve sobre el patio\nsegundo verso\n")
    fila = _sopa(client, "content:poem_index").select_one("li.fila--poema")
    assert fila.select_one("p.fila-verso").get_text() == "Llueve sobre el patio"
    assert "segundo verso" not in fila.get_text()


def test_el_primer_verso_va_escapado(client, make_poem):
    """El cuerpo lo escribe una persona: en el índice va escapado como en la ficha."""
    _publicado(make_poem, slug="xss", body="<script>alert(1)</script>\notro")
    contenido = client.get(reverse("content:poem_index")).content
    assert b"<script>alert(1)</script>" not in contenido
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in contenido


def test_un_primer_verso_muy_largo_se_corta(client, make_poem):
    """Un poema en prosa abre con un párrafo: la fila cita su arranque, no el párrafo."""
    _publicado(make_poem, slug="prosa", body="palabra " * 60)
    verso = _sopa(client, "content:poem_index").select_one("p.fila-verso").get_text()
    assert len(verso) <= 90 and verso.endswith("…")


def test_un_poema_sin_texto_no_deja_un_parrafo_vacio(client, make_poem):
    _publicado(make_poem, slug="vacio", body="   \n\n")
    assert _sopa(client, "content:poem_index").select_one("p.fila-verso") is None


def test_en_un_listado_de_poemas_la_cejilla_poema_no_se_repite(client, make_poem):
    """«Poema» en cada fila de /poemas/ no dice nada. En una colección, donde se mezclan
    con textos, sí distingue."""
    poema = _publicado(make_poem, slug="uno", title="Poema Uno")
    assert _sopa(client, "content:poem_index").select_one("li.fila .kicker") is None

    coleccion = Collection.objects.create(
        slug="mezcla", title="Mezcla", status=PublishStatus.PUBLISHED
    )
    CollectionPoem.objects.create(collection=coleccion, poem=poema, position=0)
    cejilla = _sopa(client, "content:collection_detail", "mezcla").select_one("li.fila .kicker")
    assert cejilla is not None and cejilla.get_text(strip=True) == "Poema"

    autora = Contributor.objects.create(slug="autora", display_name="Autora", is_member=True)
    PoemContributor.objects.create(poem=poema, contributor=autora)
    ficha = _sopa(client, "people:member_detail", "autora")
    assert ficha.select_one("li.fila--poema") is not None
    assert ficha.select_one("li.fila--poema .kicker") is None


# ── Anatomía de la fila ───────────────────────────────────────────────────


def test_la_fila_de_un_texto_reparte_fecha_titulo_y_firma(client, make_article):
    seccion = Section.objects.create(slug="cronica", name="Crónica")
    articulo = _publicado(
        make_article, slug="a1", title="Texto en fila", subtitle="Su bajada", section=seccion
    )
    firma = Contributor.objects.create(slug="firma", display_name="Quien Firma")
    ArticleContributor.objects.create(article=articulo, contributor=firma)

    sopa = _sopa(client, "content:text_archive")
    assert sopa.select_one("ul.filas") is not None, "la lista dejó de ser un contenedor de filas"
    fila = sopa.select_one("li.article-card.fila")
    hijos = list(fila.find_all(recursive=False))
    assert [h.name for h in hijos] == ["time", "div", "p"], "fecha, cuerpo y pie, en ese orden"

    fecha, cuerpo, pie = hijos
    assert "fila-fecha" in fecha["class"]
    assert fecha["datetime"] == articulo.published_at.strftime("%Y-%m-%d"), (
        "la fecha debe poder leerla una máquina"
    )
    assert "fila-cuerpo" in cuerpo["class"]
    assert cuerpo.select_one("h3.fila-titulo a")["href"] == articulo.get_absolute_url()
    assert cuerpo.select_one("p.dek").get_text() == "Su bajada"
    assert "fila-pie" in pie["class"]
    assert pie.select_one("a")["href"] == firma.get_absolute_url()
    assert f"{articulo.reading_time} min" in pie.get_text()


def test_la_fila_tiene_un_solo_enlace_al_texto(client, make_article):
    """Toda la fila se pulsa, pero con UN enlace: el del título, extendido por CSS. Envolver
    la fila en <a> —o repetir el enlace en la fecha— daría al lector de pantalla dos
    paradas por texto, o un enlace con el nombre de toda la fila."""
    articulo = _publicado(make_article, slug="unico", title="Un solo enlace")
    fila = _sopa(client, "content:text_archive").select_one("li.fila")
    hacia_el_texto = [a for a in fila.find_all("a") if a["href"] == articulo.get_absolute_url()]
    assert len(hacia_el_texto) == 1
    assert hacia_el_texto[0].get_text() == "Un solo enlace"
    assert fila.find_parent("a") is None


def test_sin_fecha_de_publicacion_no_se_emite_un_time_vacio(client, make_article):
    make_article(slug="sin-fecha", status=EditorialStatus.PUBLISHED, published_at=None)
    fila = _sopa(client, "content:text_archive").select_one("li.fila")
    assert fila is not None and fila.select_one("time") is None


# ── Trayectoria ───────────────────────────────────────────────────────────


def test_la_trayectoria_son_filas_y_un_hito_no_enlaza(client):
    """El hito no tiene página propia: su fila no lleva enlace, y por eso el CSS no le da
    estado al pasar el puntero (se apoya en que no hay <a> dentro del título)."""
    from datetime import timedelta

    hecho = make_event(
        slug="hecho",
        title="Recital hecho",
        starts_at=timezone.now() - timedelta(days=30),
        city="Valparaíso",
    )
    Milestone.objects.create(year=2019, title="Fundación", description="Primera lectura.")
    make_publication(slug="libro", title="Libro del año", year=2021)

    sopa = _sopa(client, "agenda:trayectoria")
    filas = {f.select_one(".fila-titulo").get_text(strip=True): f for f in sopa.select("li.fila")}
    assert set(filas) == {"Recital hecho", "Fundación", "Libro del año"}

    evento = filas["Recital hecho"]
    assert evento.select_one(".fila-titulo a")["href"] == hecho.get_absolute_url()
    assert evento.select_one("time.fila-fecha")["datetime"] == hecho.starts_at.strftime("%Y-%m-%d")
    assert "Valparaíso" in evento.select_one(".fila-pie").get_text()

    hito = filas["Fundación"]
    assert hito.find("a") is None, "un hito no tiene adónde llevar"
    assert hito.select_one(".fila-fecha").get_text() == "Hito"
    assert hito.select_one("p.dek").get_text() == "Primera lectura."

    assert filas["Libro del año"].select_one(".fila-fecha").get_text() == "Publicación"
    # Cada fila cuelga de su año, que es un h2: los títulos de fila son h3.
    assert {f.select_one(".fila-titulo").name for f in filas.values()} == {"h3"}
    assert [h.get_text() for h in sopa.select("h2.year-mark")] == sorted(
        {str(hecho.starts_at.year), "2019", "2021"}, reverse=True
    )


# ── Prensa ────────────────────────────────────────────────────────────────


def test_la_mencion_de_prensa_es_una_fila_con_su_cita(client):
    PressMention.objects.create(
        title="Con enlace",
        outlet="Radio Uno",
        url="https://example.com/nota",
        quote="Voz necesaria.",
        author="M. Torres",
        published_on=timezone.now().date(),
        position=0,
    )
    PressMention.objects.create(title="Sin enlace", outlet="Diario Dos", position=1)
    con, sin = _sopa(client, "showcase:press_index").select("li.fila")

    enlace = con.select_one("h2.fila-titulo a")
    assert enlace["href"] == "https://example.com/nota"
    assert enlace["target"] == "_blank" and "noopener" in enlace["rel"]
    assert con.select_one(".fila-cuerpo blockquote.press-quote").get_text() == "«Voz necesaria.»"
    assert con.select_one(".fila-pie").get_text(strip=True) == "Por M. Torres"
    assert con.select_one("time.fila-fecha") is not None

    assert sin.find("a") is None, "sin URL la mención se cita, no se enlaza"
    assert sin.select_one("time") is None and sin.select_one(".fila-pie") is None
