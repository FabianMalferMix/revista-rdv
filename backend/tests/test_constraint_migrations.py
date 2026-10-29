"""Las migraciones que corrigen los datos antes de cada restricción nueva.

Cada prueba vuelve su app a la migración anterior, crea con los modelos de entonces las filas que
la restricción prohibiría, migra hacia delante y comprueba qué quedó. Al terminar, la base vuelve
a la última migración.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def _migrate(app, name):
    """Lleva `app` a la migración `name` y devuelve los modelos de ese momento."""
    executor = MigrationExecutor(connection)
    executor.migrate([(app, name)])
    return executor.loader.project_state([(app, name)]).apps


@pytest.fixture(autouse=True)
def _back_to_the_latest_migrations():
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def test_public_pieces_get_a_date_and_undated_scheduled_ones_go_back_to_approved():
    old = _migrate("content", "0013_permisos_de_revisar_y_publicar")
    Article = old.get_model("content", "Article")
    fields = {"title": "Pieza", "body": "Texto", "reading_time": 1}
    published = Article.objects.create(slug="publicada", status="published", **fields)
    scheduled = Article.objects.create(slug="programada", status="scheduled", **fields)
    draft = Article.objects.create(slug="borrador", status="draft", **fields)

    new = _migrate("content", "0014_piezas_publicas_con_fecha")
    Article = new.get_model("content", "Article")
    published = Article.objects.get(pk=published.pk)
    assert published.published_at == published.updated_at
    assert Article.objects.get(pk=scheduled.pk).status == "approved"
    assert Article.objects.get(pk=draft.pk).published_at is None, "un borrador no necesita fecha"
    log = new.get_model("content", "EditorialTransition").objects.filter(object_id=scheduled.pk)
    assert list(log.values_list("from_status", "to_status")) == [("scheduled", "approved")]


def test_an_event_that_ended_before_it_started_loses_its_end():
    old = _migrate("agenda", "0001_initial")
    Event = old.get_model("agenda", "Event")
    start = timezone.now()
    wrong = Event.objects.create(
        slug="al-reves", title="E", starts_at=start, ends_at=start - timedelta(hours=1)
    )
    right = Event.objects.create(
        slug="bien", title="E", starts_at=start, ends_at=start + timedelta(hours=1)
    )

    new = _migrate("agenda", "0002_actividades_terminan_despues_de_empezar")
    Event = new.get_model("agenda", "Event")
    assert Event.objects.get(pk=wrong.pk).ends_at is None
    assert Event.objects.get(pk=right.pk).ends_at == right.ends_at


def test_a_call_with_crossed_dates_gets_them_swapped():
    old = _migrate("submissions", "0002_alter_submission_file")
    Call = old.get_model("submissions", "Call")
    start = timezone.now()
    crossed = Call.objects.create(
        slug="cruzada", title="C", opens_at=start, closes_at=start - timedelta(days=5)
    )
    instant = Call.objects.create(slug="instante", title="C", opens_at=start, closes_at=start)

    new = _migrate("submissions", "0003_convocatorias_cierran_despues_de_abrir")
    Call = new.get_model("submissions", "Call")
    crossed = Call.objects.get(pk=crossed.pk)
    assert (crossed.opens_at, crossed.closes_at) == (start - timedelta(days=5), start)
    assert Call.objects.get(pk=instant.pk).closes_at == start + timedelta(days=1)
