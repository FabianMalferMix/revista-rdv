"""Presupuesto de consultas en las vistas de alto tráfico (guardia anti-N+1).

Se siembra VOLUMEN (12 artículos/poemas, 8 eventos/registros/publicaciones) y se
afirma que cada vista se mantiene bajo un techo FIJO de consultas. Como el techo no
crece con la cantidad de piezas, una regresión N+1 (una consulta por ítem) lo
superaría de inmediato. Los techos llevan holgura sobre lo medido hoy.
"""

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.content.models import ArticleContributor, PoemContributor
from apps.people.models import Contributor
from apps.reviews.models import Publisher
from tests.factories import (
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
    "content:home": 24,  # medido 16 (el sello de convocatoria pregunta si hay una abierta)
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
        assert Client().get(reverse("content:search") + "?q=Perf").status_code == 200


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

    url = reverse("content:home")
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
