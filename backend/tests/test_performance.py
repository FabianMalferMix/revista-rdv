"""Presupuesto de consultas en las vistas de alto tráfico (guardia anti-N+1).

Se siembra VOLUMEN (12 artículos/poemas, 8 eventos/registros/publicaciones) y se
afirma que cada vista se mantiene bajo un techo FIJO de consultas. Como el techo no
crece con la cantidad de piezas, una regresión N+1 (una consulta por ítem) lo
superaría de inmediato. Los techos llevan holgura sobre lo medido hoy.
"""

import pytest
from django.test import Client
from django.urls import reverse

from tests.factories import make_event, make_publication, make_recording, publish

pytestmark = pytest.mark.django_db

# vista -> techo de consultas (medido hoy + holgura)
BUDGETS = {
    "content:home": 24,  # medido 18
    "content:text_archive": 10,  # 6
    "content:poem_index": 10,  # 6
    "people:member_index": 8,  # 4
    "agenda:agenda": 8,  # 4
    "showcase:publication_index": 10,  # 5
    "media:recording_index": 10,  # 6
    "showcase:dossier": 22,  # 16
}


@pytest.fixture
def _seed_volume(make_article, make_poem):
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


def test_article_detail_query_budget(make_article, django_assert_max_num_queries):
    art = publish(make_article(slug="perf-detalle", title="Detalle Perf"))
    with django_assert_max_num_queries(12):  # medido 7
        assert Client().get(reverse("content:article_detail", args=[art.slug])).status_code == 200


def test_search_query_budget(_seed_volume, django_assert_max_num_queries):
    with django_assert_max_num_queries(10):  # medido 6
        assert Client().get(reverse("content:search") + "?q=Perf").status_code == 200
