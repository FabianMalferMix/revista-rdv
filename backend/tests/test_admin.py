import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.content.admin import ArticleAdmin
from apps.content.models import Article, ArticleStatus

pytestmark = pytest.mark.django_db
S = ArticleStatus


def _admin():
    return ArticleAdmin(Article, AdminSite())


def _request(user):
    req = RequestFactory().get("/admin/content/article/")
    req.user = user
    return req


def test_save_model_sets_owner_on_create(autor):
    article = Article(slug="nuevo", title="Nuevo", body="cuerpo")
    _admin().save_model(_request(autor), article, form=None, change=False)
    assert article.owner == autor


def test_save_model_keeps_owner_on_edit(editor, autor, make_article):
    article = make_article(owner=autor, status=S.DRAFT)
    _admin().save_model(_request(editor), article, form=None, change=True)
    article.refresh_from_db()
    assert article.owner == autor  # editar no reasigna el dueño


def test_queryset_scoped_for_author(editor, autor, make_article):
    make_article(owner=editor, status=S.PUBLISHED)
    own = make_article(owner=autor, status=S.DRAFT)
    assert list(_admin().get_queryset(_request(autor))) == [own]


def test_queryset_full_for_editor(editor, autor, make_article):
    make_article(owner=autor, status=S.DRAFT)
    assert _admin().get_queryset(_request(editor)).count() == 1


def test_change_permission_state_scoped_for_author(autor, make_article):
    ma = _admin()
    draft = make_article(owner=autor, status=S.DRAFT)
    published = make_article(owner=autor, status=S.PUBLISHED)
    assert ma.has_change_permission(_request(autor), draft)
    assert not ma.has_change_permission(_request(autor), published)


def test_editor_can_change_any(editor, autor, make_article):
    published = make_article(owner=autor, status=S.PUBLISHED)
    assert _admin().has_change_permission(_request(editor), published)


def test_status_readonly_for_author_only(autor, editor):
    ma = _admin()
    assert "status" in ma.get_readonly_fields(_request(autor))
    assert "status" not in ma.get_readonly_fields(_request(editor))


def test_author_cannot_delete(autor, editor, make_article):
    ma = _admin()
    article = make_article(owner=autor, status=S.DRAFT)
    assert not ma.has_delete_permission(_request(autor), article)
    assert ma.has_delete_permission(_request(editor), article)
