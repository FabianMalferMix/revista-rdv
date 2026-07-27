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
