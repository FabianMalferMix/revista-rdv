"""Presupuesto de consultas en las vistas de alto tráfico (guardia anti-N+1).

Se siembra VOLUMEN (12 artículos/poemas, 8 eventos/registros/publicaciones) y se
afirma que cada vista se mantiene bajo un techo FIJO de consultas. Como el techo no
crece con la cantidad de piezas, una regresión N+1 (una consulta por ítem) lo
superaría de inmediato. Los techos llevan holgura sobre lo medido hoy.
"""

import pytest
from django.db import connection
from django.db.models import QuerySet, TextField
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.content.models import (
    Article,
    ArticleContributor,
    Collection,
    Page,
    PoemContributor,
    PublishStatus,
    ReviewedWork,
    Section,
)
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from apps.showcase.models import SiteProfile
from apps.site.feeds import FEEDS
from apps.site.sitemaps import SITEMAPS
from tests.factories import (
    SEARCH_PANEL_HEADERS,
    make_article,
    make_event,
    make_image,
    make_poem,
    make_publication,
    make_published_article,
    make_published_poem,
    make_recording,
    publish,
)

pytestmark = pytest.mark.django_db

# vista -> techo de consultas (medido hoy + holgura). «Medido» es la primera petición, la que
# cuenta la prueba: hace tres consultas más que las siguientes. Medido tras el paso 18 del
# backlog UX, que dejó las redes del colectivo en una consulta por página, y del 19, que
# añadió a la portada su línea de respaldo (+2) y contó las cifras en una consulta (-1), y del
# 20: poemas y sus firmas, la última actividad y la fecha (+4), y el perfil una vez (-1). Sin
# las cifras ni los aliados de la portada (#128), tres menos; sin la cita de prensa (#129), otra.
# El dossier del paso 22 (ticket 5.1) hace dos menos aunque enseña retratos, cubiertas, logos y
# la fecha de actualización: dejó de precargar participantes que no enseñaba.
BUDGETS = {
    "site:home": 24,  # medido 16 (el sello de convocatoria pregunta si hay una abierta)
    "content:text_archive": 10,  # 8
    "content:poem_index": 10,  # 8
    "people:member_index": 8,  # 6
    "agenda:agenda": 8,  # 6
    "showcase:publication_index": 10,  # 7
    "media:recording_index": 10,  # 8
    "showcase:dossier": 22,  # 15
}


@pytest.fixture
def _seed_volume():
    for i in range(12):
        publish(make_article(slug=f"perf-a{i}", title=f"Artículo Perf {i}"))
        publish(make_poem(slug=f"perf-p{i}", title=f"Poema Perf {i}"))
    for i in range(8):
        make_event(slug=f"perf-e{i}", title=f"Evento Perf {i}")
        make_recording(slug=f"perf-r{i}", title=f"Registro Perf {i}")
        make_publication(slug=f"perf-pub{i}", title=f"Publicación Perf {i}")


@pytest.mark.parametrize("view_name", list(BUDGETS))
def test_hot_view_stays_within_query_budget(view_name, _seed_volume, django_assert_max_num_queries):
    with django_assert_max_num_queries(BUDGETS[view_name]):
        assert Client().get(reverse(view_name)).status_code == 200


def test_article_detail_query_budget(django_assert_max_num_queries):
    art = publish(make_article(slug="perf-detalle", title="Detalle Perf"))
    with django_assert_max_num_queries(12):  # medido 11
        assert Client().get(reverse("content:article_detail", args=[art.slug])).status_code == 200


def test_search_query_budget(_seed_volume, django_assert_max_num_queries):
    # Medido 8 tras el ticket 5.4: textos y poemas sin precargar sus autores (-2) y los
    # cuatro tipos por nombre en una sola consulta (+1). Eran 9 con solo textos y poemas.
    with django_assert_max_num_queries(10):  # medido 8
        assert Client().get(reverse("site:search") + "?q=Perf").status_code == 200


def test_the_home_costs_the_same_with_one_piece_of_each_or_four(client):
    """La portada con una pieza de cada cosa y con cuatro hace las mismas consultas: las tapas y
    las editoriales del estante, los retratos de las voces, las firmas de la obra y los pósters y
    las voces de la tirada llegan con la consulta de su lista o en un lote. El techo de arriba no
    lo vigila, porque se siembra sin nada de eso."""

    def seed(n):
        voice = Contributor.objects.create(
            slug=f"voz-{n}",
            display_name=f"Voz {n}",
            is_member=True,
            position=n,
            photo=make_image(f"retrato-{n}"),
        )
        publisher = Publisher.objects.create(slug=f"editorial-{n}", name=f"Editorial {n}")
        make_publication(
            slug=f"libro-{n}",
            title=f"Libro {n}",
            position=n,
            cover=make_image(f"tapa-{n}"),
            publisher=publisher,
        )
        article = make_published_article(slug=f"texto-{n}", cover_image=make_image(f"imagen-{n}"))
        ArticleContributor.objects.create(article=article, contributor=voice)
        poem = make_published_poem(slug=f"poema-{n}")
        PoemContributor.objects.create(poem=poem, contributor=voice)
        recording = make_recording(
            slug=f"lectura-{n}", featured=True, position=n, poster=make_image(f"afiche-{n}")
        )
        recording.participants.add(voice)

    url = reverse("site:home")
    seed(0)
    client.get(url)  # en caliente: el perfil ya existe
    with CaptureQueriesContext(connection) as one:
        client.get(url)
    for n in (1, 2, 3):
        seed(n)
    with CaptureQueriesContext(connection) as four:
        page = client.get(url).content.decode()
    # Control: la portada enseña lo sembrado de la última tanda.
    assert "Editorial 3" in page and "Voz 3" in page and "Libro 3" in page
    assert len(four) == len(one), "una consulta más por pieza"


def _profile_reads(queries):
    return sum('FROM "showcase_siteprofile"' in query["sql"] for query in queries)


@pytest.mark.parametrize(
    "view_name", ["site:home", "showcase:dossier", "agenda:trayectoria", "feed", "recordings_feed"]
)
def test_a_page_reads_the_profile_once(client, view_name):
    """La vista, las plantillas y el feed leen el mismo perfil: una consulta por petición."""
    SiteProfile.load()  # en caliente: el perfil ya existe
    with CaptureQueriesContext(connection) as queries:
        assert client.get(reverse(view_name)).status_code == 200
    assert _profile_reads(queries) == 1


def test_the_search_panel_does_not_read_the_profile(client):
    """El fragmento que pide la lupa no lleva cabecera ni pie: no paga el perfil."""
    SiteProfile.load()
    make_published_article(title="La zarzamora")
    url = reverse("site:search") + "?q=zarzamora"
    with CaptureQueriesContext(connection) as panel:
        found = client.get(url, headers=SEARCH_PANEL_HEADERS).content.decode()
    assert "La zarzamora" in found  # control: la búsqueda corrió
    # Control: la página entera de la búsqueda sí lo lee, una vez.
    with CaptureQueriesContext(connection) as page:
        assert client.get(url).status_code == 200
    assert (_profile_reads(panel), _profile_reads(page)) == (0, 1)


def _seed_listed(n):
    """Una pieza de cada cosa que listan el sitemap y los feeds, firmada y reseñada. Devuelve
    las direcciones que el sitemap tiene que enseñar."""
    section = Section.objects.create(slug=f"seccion-{n}", name=f"Sección {n}")
    guest = Contributor.objects.create(slug=f"firma-{n}", display_name=f"Firma {n}")
    member = Contributor.objects.create(
        slug=f"integrante-{n}", display_name=f"Integrante {n}", is_member=True
    )
    article = make_published_article(slug=f"texto-{n}", section=section)
    ArticleContributor.objects.create(article=article, contributor=guest)
    poem = make_published_poem(slug=f"poema-{n}")
    PoemContributor.objects.create(poem=poem, contributor=member, position=1)
    publisher = Publisher.objects.create(slug=f"editorial-{n}", name=f"Editorial {n}")
    author = BookAuthor.objects.create(slug=f"autora-{n}", name=f"Autora {n}")
    work = Work.objects.create(slug=f"obra-{n}", title=f"Obra {n}", publisher=publisher)
    work.authors.add(author)
    ReviewedWork.objects.create(article=article, work=work)
    pieces = [
        section,
        guest,
        member,
        article,
        poem,
        publisher,
        author,
        work,
        Collection.objects.create(
            slug=f"coleccion-{n}", title=f"Colección {n}", status=PublishStatus.PUBLISHED
        ),
        Page.objects.create(
            slug=f"pagina-{n}", title=f"Página {n}", body="<p>x</p>", status=PublishStatus.PUBLISHED
        ),
        make_event(slug=f"actividad-{n}"),
        make_publication(slug=f"libro-{n}"),
        make_recording(slug=f"lectura-{n}", kind=Recording.Kind.AUDIO),
    ]
    return [piece.get_absolute_url() for piece in pieces]


def _listed_models(name):
    """Los modelos de lo que lista el sitemap o un feed."""
    listings = (
        [s().items() for s in SITEMAPS.values()] if name == "sitemap" else [FEEDS[name].items()]
    )
    return {items.model for items in listings if isinstance(items, QuerySet)}


# Lo largo que escribe cada feed: la entradilla de cada texto y la descripción de cada registro.
WRITTEN_TEXT = {"feed": {(Article, "excerpt")}, "recordings_feed": {(Recording, "description")}}


@pytest.mark.parametrize("name", ["sitemap", "feed", "recordings_feed"])
def test_a_listing_does_not_read_the_long_text_of_what_it_lists(client, name):
    """El sitemap y los feeds leen de cada pieza solo lo que escriben: las filas enteras llevan
    el cuerpo de cada texto, la transcripción de cada registro y la biografía de cada firma."""
    article_url = _seed_listed(0)[3]
    SiteProfile.load()
    models = _listed_models(name)
    long_columns = {
        f'"{model._meta.db_table}"."{field.column}"'
        for model in models
        for field in model._meta.concrete_fields
        if isinstance(field, TextField) and (model, field.name) not in WRITTEN_TEXT.get(name, ())
    }
    with CaptureQueriesContext(connection) as queries:
        assert client.get(reverse(name)).status_code == 200
    sql = " ".join(query["sql"] for query in queries)
    # Control: el listado consultó la tabla de cada cosa que lista.
    assert all(f'FROM "{model._meta.db_table}"' in sql for model in models)
    assert {column for column in long_columns if column in sql} == set()
    # Control: la ficha de un texto sí lee su cuerpo, y así se escribe en la consulta.
    with CaptureQueriesContext(connection) as page:
        assert client.get(article_url).status_code == 200
    assert '"content_article"."body"' in " ".join(query["sql"] for query in page)


@pytest.mark.parametrize("name", ["sitemap", "feed", "recordings_feed"])
def test_a_listing_costs_the_same_with_one_piece_of_each_or_three(
    client, name, django_capture_on_commit_callbacks
):
    """Lo que la dirección de cada pieza pide viene en la consulta de su lista: un campo que
    faltara costaría una consulta por pieza. Cada siembra se confirma, como en el panel, para que
    el listado no salga de su caché."""
    SiteProfile.load()
    with django_capture_on_commit_callbacks(execute=True):
        _seed_listed(0)
    with CaptureQueriesContext(connection) as one:
        assert client.get(reverse(name)).status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        _seed_listed(1)
        last = _seed_listed(2)
    with CaptureQueriesContext(connection) as three:
        body = client.get(reverse(name)).content.decode()
    # Control: el listado enseña lo de la última siembra (el feed, el texto; el pódcast, el registro).
    expected = {"sitemap": last, "feed": [last[3]], "recordings_feed": [last[-1]]}[name]
    assert [url for url in expected if url not in body] == []
    assert len(three) == len(one), "una consulta más por pieza"


def test_a_publisher_page_costs_the_same_with_one_publication_or_ten(client):
    """Cada tarjeta nombra la editorial de su publicación, que llega en la consulta de la lista."""
    publisher = Publisher.objects.create(slug="editorial-z", name="Editorial Z")
    url = publisher.get_absolute_url()
    make_publication(slug="libro-0", title="Libro 0", publisher=publisher)
    SiteProfile.load()
    with CaptureQueriesContext(connection) as one:
        assert client.get(url).status_code == 200
    for n in range(1, 10):
        make_publication(slug=f"libro-{n}", title=f"Libro {n}", publisher=publisher)
    with CaptureQueriesContext(connection) as ten:
        page = client.get(url).content.decode()
    assert "Libro 9" in page  # control: la ficha enseña las diez
    assert len(ten) == len(one), "una consulta más por publicación"


@pytest.mark.parametrize("model", ["publication", "recording"])
def test_an_index_does_not_read_who_takes_part_and_the_page_does(client, model):
    """Las tarjetas de los índices no dicen quién participa; la ficha, sí."""
    voice = Contributor.objects.create(slug="voz", display_name="Voz Participante", is_member=True)
    if model == "publication":
        piece, index = make_publication(slug="libro"), reverse("showcase:publication_index")
    else:
        piece, index = make_recording(slug="lectura"), reverse("media:recording_index")
    piece.participants.add(voice)
    table = f'"{piece.participants.through._meta.db_table}"'
    with CaptureQueriesContext(connection) as listing:
        assert piece.get_absolute_url() in client.get(index).content.decode()
    with CaptureQueriesContext(connection) as page:
        assert "Voz Participante" in client.get(piece.get_absolute_url()).content.decode()

    def reads(queries):
        return any(table in query["sql"] for query in queries)

    assert (reads(listing), reads(page)) == (False, True)
