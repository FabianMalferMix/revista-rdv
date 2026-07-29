from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.content import workflow
from apps.content.models import EditorialStatus, EditorialTransition
from apps.content.tasks import publish_due_items

pytestmark = pytest.mark.django_db
S = EditorialStatus


def test_author_can_submit_own(autor, make_article):
    article = make_article(owner=autor, status=S.DRAFT)
    workflow.perform_transition(article, "submit", autor)
    assert article.status == S.IN_REVIEW


def test_author_cannot_publish(autor, make_article):
    article = make_article(owner=autor, status=S.APPROVED)
    with pytest.raises(PermissionDenied):
        workflow.perform_transition(article, "publish", autor)


def test_author_cannot_accept_own(autor, make_article):
    article = make_article(owner=autor, status=S.IN_REVIEW)
    with pytest.raises(PermissionDenied):
        workflow.perform_transition(article, "accept", autor)


def test_editor_publish_sets_published_at(editor, autor, make_article):
    article = make_article(owner=autor, status=S.APPROVED)
    assert article.published_at is None
    workflow.perform_transition(article, "publish", editor)
    assert article.status == S.PUBLISHED
    assert article.published_at is not None


def test_invalid_transition_from_state(editor, make_article):
    article = make_article(status=S.DRAFT)
    with pytest.raises(ValueError):
        workflow.perform_transition(article, "publish", editor)  # no se publica desde borrador


def test_unknown_transition(editor, make_article):
    article = make_article(status=S.DRAFT)
    with pytest.raises(ValueError):
        workflow.perform_transition(article, "teleport", editor)


def test_transition_writes_audit_trail(editor, autor, make_article):
    article = make_article(owner=autor, status=S.IN_REVIEW)
    workflow.perform_transition(article, "accept", editor, note="ok")
    entry = EditorialTransition.objects.filter(article=article).latest("created_at")
    assert (entry.from_status, entry.to_status) == (S.IN_REVIEW, S.APPROVED)
    assert entry.actor == editor
    assert entry.note == "ok"


def test_available_transitions_for_editor_in_review(editor, autor, make_article):
    article = make_article(owner=autor, status=S.IN_REVIEW)
    available = set(workflow.available_transitions(editor, article))
    assert {"accept", "reject", "request_changes"} <= available


def test_available_transitions_for_author_draft(autor, make_article):
    article = make_article(owner=autor, status=S.DRAFT)
    assert workflow.available_transitions(autor, article) == ["submit"]


def test_publish_due_items_task(make_article):
    article = make_article(status=S.SCHEDULED)
    article.published_at = timezone.now() - timedelta(minutes=1)
    article.save(update_fields=["published_at"])
    published = publish_due_items()
    article.refresh_from_db()
    assert published >= 1
    assert article.status == S.PUBLISHED


def test_publish_due_items_is_idempotent(make_article):
    # Una pieza vencida se publica una vez; una segunda corrida no la re-publica
    # ni duplica la bitácora (idempotencia contra doble beat / reintento acks_late).
    article = make_article(status=S.SCHEDULED)
    article.published_at = timezone.now() - timedelta(minutes=1)
    article.save(update_fields=["published_at"])

    assert publish_due_items() == 1
    assert publish_due_items() == 0
    assert EditorialTransition.objects.filter(article=article, to_status=S.PUBLISHED).count() == 1


def test_schedule_requires_future_published_at(editor, make_article):
    # Sin fecha: rechazado (si no, quedaría SCHEDULED para siempre sin publicarse).
    article = make_article(status=S.APPROVED)
    assert article.published_at is None
    with pytest.raises(ValueError):
        workflow.perform_transition(article, "schedule", editor)
    article.refresh_from_db()
    assert article.status == S.APPROVED  # no transicionó

    # Con fecha pasada: también rechazado.
    article.published_at = timezone.now() - timedelta(minutes=5)
    article.save(update_fields=["published_at"])
    with pytest.raises(ValueError):
        workflow.perform_transition(article, "schedule", editor)

    # Con fecha futura: programa correctamente.
    article.published_at = timezone.now() + timedelta(days=1)
    article.save(update_fields=["published_at"])
    workflow.perform_transition(article, "schedule", editor)
    assert article.status == S.SCHEDULED


def test_perform_transition_rechecks_state_under_lock(editor, make_article):
    # Dos instancias de la misma pieza; una queda obsoleta en memoria. Tras publicar
    # por una vía, el re-chequeo autoritativo bajo lock frena la segunda transición
    # y no duplica la bitácora (cierre del TOCTOU de perform_transition).
    article = make_article(status=S.SCHEDULED)
    stale = type(article).objects.get(pk=article.pk)

    workflow.perform_transition(article, "publish", editor)
    with pytest.raises(ValueError):
        workflow.perform_transition(stale, "publish", editor)

    assert EditorialTransition.objects.filter(article=article, to_status=S.PUBLISHED).count() == 1


def test_publish_due_items_declares_resilience_policy():
    """La tarea de publicación programada reintenta ante errores transitorios de BD y
    usa acks_late (si el worker muere, la tarea se re-encola en vez de perderse)."""
    from django.db import OperationalError

    assert OperationalError in publish_due_items.autoretry_for
    assert publish_due_items.retry_kwargs["max_retries"] == 3
    assert publish_due_items.acks_late is True
