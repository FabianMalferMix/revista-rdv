"""Índices como filas tipográficas.

Textos, poemas, trayectoria y prensa son filas con un dato a cada lado del título, y la fila
entera es el enlace: tarjetas apiladas con todo pegado a la izquierda dejarían, en el carril
ancho, dos tercios de la pantalla vacíos. El título de la fila es un h2 bajo el h1 de un índice
y un h3 bajo el h2 de una sección; la hoja le da la tipografía de titular por su clase, nunca
por su etiqueta. Lo que solo se ve al pintar (anchos, estados) se comprueba aparte, sobre la
hoja de estilos y con tools/ux.
"""

import re

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Milestone
from apps.content.models import (
    ArticleContributor,
    Collection,
    CollectionArticle,
    CollectionPoem,
    PoemContributor,
    PublishStatus,
    Section,
    Tag,
)
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from apps.showcase.models import PressMention
from tests import css
from tests.factories import (
    make_event,
    make_publication,
    make_published_article,
    make_published_poem,
    soup,
)

pytestmark = pytest.mark.django_db


def _sopa(client, nombre, *args):
    return soup(client, reverse(nombre, args=args))


# ── El primer verso ───────────────────────────────────────────────────────


def test_la_fila_del_poema_cita_su_primer_verso(client):
    """La fila cita el primer verso: es lo que permite reconocer un poema sin abrirlo, como
    en el índice de primeros versos de una antología."""
    make_published_poem(slug="patio", body="\n   Llueve sobre el patio\nsegundo verso\n")
    fila = _sopa(client, "content:poem_index").select_one("li.fila--poema")
    assert fila.select_one("p.fila-verso").get_text() == "Llueve sobre el patio"
    assert "segundo verso" not in fila.get_text()


def test_el_primer_verso_va_escapado(client):
    """El cuerpo lo escribe una persona: en el índice va escapado como en la ficha."""
    make_published_poem(slug="xss", body="<script>alert(1)</script>\notro")
    contenido = client.get(reverse("content:poem_index")).content
    assert b"<script>alert(1)</script>" not in contenido
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in contenido


def test_un_primer_verso_muy_largo_se_corta(client):
    """Un poema en prosa abre con un párrafo: la fila cita su arranque, no el párrafo."""
    make_published_poem(slug="prosa", body="palabra " * 60)
    verso = _sopa(client, "content:poem_index").select_one("p.fila-verso").get_text()
    assert len(verso) <= 90 and verso.endswith("…")


def test_la_portada_no_se_llena_con_un_poema_en_prosa(client):
    make_published_poem(slug="prosa", body=("Un párrafo de prosa muy largo. " * 30 + "\n") * 3)
    sopa = BeautifulSoup(client.get(reverse("site:home")).content, "html.parser")
    citado = sopa.select_one("li.fila--poema .fila-versos").get_text()
    assert len(citado) <= 162 and citado.endswith("…")


def test_un_poema_sin_texto_no_deja_un_parrafo_vacio(client):
    poem = make_published_poem(slug="vacio", body="   \n\n")
    row = _sopa(client, "content:poem_index").select_one("li.fila--poema")
    assert row.select_one(".fila-titulo a")["href"] == poem.get_absolute_url()  # control
    assert row.select_one("p.fila-verso") is None


def test_en_un_listado_de_poemas_la_cejilla_poema_no_se_repite(client):
    """«Poema» en cada fila de /poemas/ no dice nada. En una colección, donde se mezclan
    con textos, sí distingue."""
    poema = make_published_poem(slug="uno", title="Poema Uno")
    row = _sopa(client, "content:poem_index").select_one("li.fila")
    assert row.select_one(".fila-titulo").get_text(strip=True) == "Poema Uno"  # control
    assert row.select_one(".kicker") is None

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


def test_la_fila_de_un_texto_reparte_fecha_titulo_y_firma(client):
    seccion = Section.objects.create(slug="cronica", name="Crónica")
    articulo = make_published_article(
        slug="a1", title="Texto en fila", subtitle="Su bajada", section=seccion
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
    assert fecha["datetime"] == timezone.localtime(articulo.published_at).strftime("%Y-%m-%d"), (
        "la fecha debe poder leerla una máquina"
    )
    assert "fila-cuerpo" in cuerpo["class"]
    assert cuerpo.select_one(".fila-titulo a")["href"] == articulo.get_absolute_url()
    assert cuerpo.select_one("p.dek").get_text() == "Su bajada"
    assert "fila-pie" in pie["class"]
    assert pie.select_one("a")["href"] == firma.get_absolute_url()
    assert f"{articulo.reading_time} min" in pie.get_text()


def test_la_fila_tiene_un_solo_enlace_al_texto(client):
    """Toda la fila se pulsa, pero con UN enlace: el del título, extendido por CSS. Envolver
    la fila en <a> —o repetir el enlace en la fecha— daría al lector de pantalla dos
    paradas por texto, o un enlace con el nombre de toda la fila."""
    articulo = make_published_article(slug="unico", title="Un solo enlace")
    fila = _sopa(client, "content:text_archive").select_one("li.fila")
    hacia_el_texto = [a for a in fila.find_all("a") if a["href"] == articulo.get_absolute_url()]
    assert len(hacia_el_texto) == 1
    assert hacia_el_texto[0].get_text() == "Un solo enlace"
    assert fila.find_parent("a") is None


# ── El título de la fila ──────────────────────────────────────────────────


def test_card_titles_sit_one_level_below_the_heading_they_hang_from(client):
    """Quien recorre una página por sus encabezados no se salta ningún nivel: bajo el h1 de un
    índice, el título de cada tarjeta es un h2; bajo el h2 de una sección (los textos de una
    integrante, las reseñas de una obra, la obra de la portada), un h3."""
    section = Section.objects.create(slug="cronica", name="Crónica")
    tag = Tag.objects.create(slug="ciudad", name="Ciudad")
    member = Contributor.objects.create(
        slug="integrante", display_name="Integrante", is_member=True
    )
    guest = Contributor.objects.create(slug="invitada", display_name="Invitada")
    publisher = Publisher.objects.create(slug="editorial", name="Editorial")
    author = BookAuthor.objects.create(slug="autora", name="Autora")
    book = make_publication(slug="libro", title="Libro")
    work = Work.objects.create(slug="obra", title="Obra", publisher=publisher, publicacion=book)
    work.authors.add(author)
    collection = Collection.objects.create(
        slug="coleccion", title="Colección", status=PublishStatus.PUBLISHED
    )
    for person in (member, guest):
        article = make_published_article(slug=f"texto-{person.slug}", section=section)
        article.tags.add(tag)
        article.reviewed_works.add(work)
        ArticleContributor.objects.create(article=article, contributor=person)
        poem = make_published_poem(slug=f"poema-{person.slug}")
        PoemContributor.objects.create(poem=poem, contributor=person)
        CollectionArticle.objects.create(collection=collection, article=article)
        CollectionPoem.objects.create(collection=collection, poem=poem, position=1)

    pages = [
        reverse("content:text_archive"),
        reverse("content:poem_index"),
        section.get_absolute_url(),
        tag.get_absolute_url(),
        collection.get_absolute_url(),
        member.get_absolute_url(),
        guest.get_absolute_url(),
        work.get_absolute_url(),
        publisher.get_absolute_url(),
        author.get_absolute_url(),
        book.get_absolute_url(),
        reverse("site:home"),
    ]
    levels = {f"h{n}": n for n in range(1, 7)}
    for url in pages:
        headings = soup(client, url).select("main :is(h1, h2, h3, h4, h5, h6)")
        cards = [h for h in headings if h.find_parent("li", class_="article-card")]
        assert cards, f"control: {url} no enseña ninguna tarjeta"
        for card in cards:
            above = [h for h in headings[: headings.index(card)] if h not in cards]
            assert levels[card.name] == levels[above[-1].name] + 1, (
                f"en {url}, «{card.get_text(strip=True)}» es un {card.name} bajo el "
                f"{above[-1].name} «{above[-1].get_text(strip=True)}»"
            )


def _card_titles(client):
    """Los títulos de las tarjetas de texto y de poema tal como salen bajo el h1 de un índice y
    bajo el h2 de una sección (la ficha de una integrante), donde cambian de etiqueta. El titular
    de la tarjeta es la superficie donde más se repite la tipografía de titular del sitio."""
    member = Contributor.objects.create(slug="firma", display_name="Firma", is_member=True)
    article = make_published_article(slug="tarjeta-texto")
    ArticleContributor.objects.create(article=article, contributor=member)
    poem = make_published_poem(slug="tarjeta-poema")
    PoemContributor.objects.create(poem=poem, contributor=member)
    titles = []
    for url in (
        reverse("content:text_archive"),
        reverse("content:poem_index"),
        member.get_absolute_url(),
    ):
        cards = soup(client, url).select("li.article-card")
        assert cards, f"control: {url} no enseña ninguna tarjeta"
        titles += [card.find(re.compile(r"^h[1-6]$")) for card in cards]
    return titles


def _selectores_de_titular():
    """Los selectores de las reglas que fijan font-family:var(--display)."""
    selectores = {
        selector
        for regla in css.rules()
        if regla.context == () and regla.get("font-family") == "var(--display)"
        for selector in regla.selectors
    }
    assert selectores, "no se encontró la regla que fija la tipografía de titular"
    return selectores


def test_titulo_de_tarjeta_usa_la_tipografia_de_titular(client):
    """El CSS nombra lo que las tarjetas emiten de verdad: la clase de su título, que es un h2 o
    un h3 según dónde va la lista. Una regla que apunta a algo que las tarjetas no emiten no da
    error: no se aplica, y los títulos de todos los listados caen a la serif del cuerpo."""
    titles = _card_titles(client)
    assert {title.name for title in titles} == {"h2", "h3"}, "control: las dos alturas"
    assert all("fila-titulo" in title["class"] for title in titles), "un título sin su clase"
    assert ".fila-titulo" in _selectores_de_titular(), (
        "la regla de titulares no cubre el título de las tarjetas: caerá a la serif del cuerpo"
    )


def test_no_rule_styles_the_card_title_by_its_tag(client):
    """El título de la tarjeta es un h2 o un h3 según dónde va la lista: una regla que lo
    alcanzara por su etiqueta (`.article-card h3`) se aplicaría en unas páginas y en otras no,
    sin dar error. Su familia, su tamaño y su enlace van por la clase, que las tarjetas llevan
    en las dos alturas."""
    by_tag = sorted(
        selector
        for rule in css.rules()
        for selector in rule.selectors
        if re.search(r"\.(article-card|filas?)\b.*(?<![\w.#-])h[1-6](?![\w-])", selector)
    )
    assert not by_tag, f"reglas que alcanzan el título de la tarjeta por su etiqueta: {by_tag}"
    # Control: la hoja lo estiliza por la clase, y las tarjetas la llevan en sus dos alturas.
    assert css.rule((), ".fila-titulo")["font-size"] == "var(--t3)"
    assert css.rule((), ".fila-titulo a")["color"] == "var(--ink)"
    titles = _card_titles(client)
    assert {title.name for title in titles} == {"h2", "h3"}
    assert all("fila-titulo" in title["class"] for title in titles)


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
    cuando = timezone.localtime(hecho.starts_at).strftime("%Y-%m-%d")
    assert evento.select_one("time.fila-fecha")["datetime"] == cuando
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
