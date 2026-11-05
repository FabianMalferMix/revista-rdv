import pytest

from apps.content import permissions
from apps.content.models import EditorialStatus
from tests.factories import make_article

pytestmark = pytest.mark.django_db
S = EditorialStatus


def test_owner_can_edit_draft(autor):
    article = make_article(owner=autor, status=S.DRAFT)
    assert permissions.can_edit_item(autor, article)


def test_owner_can_edit_changes_requested(autor):
    article = make_article(owner=autor, status=S.CHANGES_REQUESTED)
    assert permissions.can_edit_item(autor, article)


def test_owner_cannot_edit_in_review(autor):
    # El permiso depende del estado, no solo del rol.
    article = make_article(owner=autor, status=S.IN_REVIEW)
    assert not permissions.can_edit_item(autor, article)


def test_owner_cannot_edit_published(autor):
    article = make_article(owner=autor, status=S.PUBLISHED)
    assert not permissions.can_edit_item(autor, article)


def test_editor_can_edit_any_state(editor, autor):
    article = make_article(owner=autor, status=S.PUBLISHED)
    assert permissions.can_edit_item(editor, article)


def test_non_owner_cannot_edit(autor, django_user_model):
    other = django_user_model.objects.create_user("otro", password="pw")
    article = make_article(owner=autor, status=S.DRAFT)
    assert not permissions.can_edit_item(other, article)


def test_is_editor_flags(editor, autor):
    assert permissions.is_editor(editor)
    assert not permissions.is_editor(autor)
