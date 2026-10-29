"""Una sola forma de publicar: la programada y la manual pasan por `perform_transition`.

Para cada tipo de pieza, las dos dejan la misma bitácora y los mismos efectos. Programar pide la
fecha en una página intermedia del panel, publicar antes de tiempo fija la fecha en ese momento, y
lo publicado, programado o archivado no se puede guardar sin fecha: el panel lo dice en el
formulario, sin un 500. Registros y colecciones toman fecha al publicarse.
"""

from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Event
from apps.content import workflow
from apps.content.models import Collection, EditorialStatus, PublishStatus, editorial_models
from apps.content.tasks import publish_due_items
from apps.submissions.models import Call
from tests.factories import make_recording

pytestmark = pytest.mark.django_db
S = EditorialStatus
EDITORIAL_MODELS = editorial_models()


def _piece(model, **fields):
    return model.objects.create(
        slug=f"{model._meta.model_name}-{model.objects.count()}",
        title="Pieza",
        body="Texto",
        **fields,
    )


def _log(piece):
    return list(piece.transitions.values_list("from_status", "to_status", "actor"))


def test_there_are_pieces_to_check():
    assert {model._meta.label for model in EDITORIAL_MODELS} >= {"content.Article", "content.Poem"}


@pytest.mark.parametrize("model", EDITORIAL_MODELS, ids=lambda model: model._meta.model_name)
def test_the_scheduled_publication_leaves_what_the_manual_one_leaves(model, editor):
    due = timezone.now() - timedelta(minutes=1)
    scheduled = _piece(model, status=S.SCHEDULED, published_at=due)
    approved = _piece(model, status=S.APPROVED)

    assert publish_due_items() == 1
    workflow.perform_transition(approved, "publish", editor)

    for piece, source, actor in ((scheduled, S.SCHEDULED, None), (approved, S.APPROVED, editor.pk)):
        piece.refresh_from_db()
        assert piece.status == S.PUBLISHED
        assert _log(piece) == [(source, S.PUBLISHED, actor)]
        assert model.objects.published().filter(pk=piece.pk).exists()
    # La programada conserva su fecha; la manual, la del momento en que se publicó.
    assert scheduled.published_at == due
    assert approved.published_at is not None and approved.published_at <= timezone.now()
    assert publish_due_items() == 0, "la segunda corrida no vuelve a publicar"


@pytest.mark.parametrize("model", EDITORIAL_MODELS, ids=lambda model: model._meta.model_name)
def test_publishing_ahead_of_time_dates_the_piece_now(model, editor):
    piece = _piece(model, status=S.SCHEDULED, published_at=timezone.now() + timedelta(days=3))
    workflow.perform_transition(piece, "publish", editor)
    assert piece.published_at <= timezone.now()


@pytest.mark.parametrize("model", EDITORIAL_MODELS, ids=lambda model: model._meta.model_name)
def test_unscheduling_keeps_the_date_and_reopening_returns_to_draft(model, editor):
    when = timezone.now() + timedelta(days=3)
    scheduled = _piece(model, status=S.SCHEDULED, published_at=when)
    workflow.perform_transition(scheduled, "unschedule", editor)
    assert (scheduled.status, scheduled.published_at) == (S.APPROVED, when)
    rejected = _piece(model, status=S.REJECTED)
    workflow.perform_transition(rejected, "reopen", editor)
    assert rejected.status == S.DRAFT


def test_scheduling_from_the_panel_asks_for_the_date(client, editor, make_article):
    article = make_article(status=S.APPROVED)
    url = reverse("admin:content_article_changelist")
    client.force_login(editor)
    action = {"action": "do_schedule", "_selected_action": [article.pk]}

    page = client.post(url, action)
    assert page.status_code == 200
    assert 'type="datetime-local"' in page.content.decode()

    past = (timezone.localtime() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    page = client.post(url, {**action, "apply": "1", "published_at": past})
    assert "La fecha tiene que ser futura." in page.content.decode()
    article.refresh_from_db()
    assert article.status == S.APPROVED

    tomorrow = timezone.localtime() + timedelta(days=1)
    response = client.post(
        url, {**action, "apply": "1", "published_at": tomorrow.strftime("%Y-%m-%dT%H:%M")}
    )
    assert response.status_code == 302
    article.refresh_from_db()
    assert article.status == S.SCHEDULED
    chosen = timezone.localtime(article.published_at)
    assert chosen.strftime("%Y-%m-%d %H:%M") == tomorrow.strftime("%Y-%m-%d %H:%M")


def _form_data(page, form_id):
    """Lo que enviaría el formulario del panel tal como se dibuja."""
    form = BeautifulSoup(page.content, "html.parser").select_one(f"form#{form_id}")
    data = {}
    for field in form.select("input[name], textarea[name], select[name]"):
        if field.get("type") in {"submit", "checkbox", "file"} or field["name"].startswith("_"):
            continue
        if field.name == "select":
            chosen = [option["value"] for option in field.select("option[selected]")]
            if field.has_attr("multiple"):
                if chosen:
                    data[field["name"]] = chosen
                continue
            data[field["name"]] = chosen[0] if chosen else ""
        else:
            data[field["name"]] = field.text if field.name == "textarea" else field.get("value", "")
    return data


def test_the_panel_will_not_save_a_scheduled_piece_without_a_date(client, editor, make_article):
    when = timezone.now() + timedelta(days=2)
    article = make_article(status=S.SCHEDULED, published_at=when)
    url = reverse("admin:content_article_change", args=[article.pk])
    client.force_login(editor)
    data = _form_data(client.get(url), "article_form")
    assert "published_at_0" in data, "control: el formulario trae la fecha"
    data.update(published_at_0="", published_at_1="")
    response = client.post(url, data)
    assert response.status_code == 200
    assert "necesita fecha de publicación" in response.content.decode()
    article.refresh_from_db()
    assert article.published_at == when


def test_recordings_and_collections_are_dated_when_published():
    recording = make_recording(slug="sin-fecha", published=False, published_at=None)
    assert recording.published_at is None
    recording.published = True
    recording.save()
    assert recording.published_at is not None
    collection = Collection.objects.create(slug="c", title="Colección", status=PublishStatus.DRAFT)
    assert collection.published_at is None
    collection.status = PublishStatus.PUBLISHED
    collection.save()
    assert collection.published_at is not None


def test_events_and_calls_cannot_end_before_they_start():
    start = timezone.now()
    event = Event(
        slug="al-reves", title="Al revés", starts_at=start, ends_at=start - timedelta(hours=1)
    )
    with pytest.raises(ValidationError, match="no puede terminar antes de empezar"):
        event.full_clean()
    call = Call(slug="c", title="C", opens_at=start, closes_at=start)
    with pytest.raises(ValidationError, match="tiene que cerrar después de abrir"):
        call.full_clean()
