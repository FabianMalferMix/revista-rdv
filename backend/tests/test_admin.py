import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.content.admin import ArticleAdmin
from apps.content.models import Article, EditorialStatus

pytestmark = pytest.mark.django_db
S = EditorialStatus


def _admin():
    return ArticleAdmin(Article, AdminSite())


def _request(user, with_messages=False):
    req = RequestFactory().get("/admin/content/article/")
    req.user = user
    if with_messages:
        from django.contrib.messages.storage.fallback import FallbackStorage

        req.session = {}
        req._messages = FallbackStorage(req)
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


def test_status_always_readonly_published_at_author_only(autor, editor):
    ma = _admin()
    # status es readonly para TODOS (solo cambia por acciones de transición).
    assert "status" in ma.get_readonly_fields(_request(autor))
    assert "status" in ma.get_readonly_fields(_request(editor))
    # published_at: readonly para el autor; editable para el editor (programación).
    assert "published_at" in ma.get_readonly_fields(_request(autor))
    assert "published_at" not in ma.get_readonly_fields(_request(editor))


def test_all_transition_actions_registered():
    ma = _admin()
    for name in [
        "do_submit",
        "do_request_changes",
        "do_accept",
        "do_reject",
        "do_schedule",
        "do_publish",
        "do_unpublish",
        "do_archive",
        "do_restore",
    ]:
        assert callable(getattr(ma, name, None)), name


def test_publish_action_transitions_and_logs(editor, autor, make_article):
    article = make_article(owner=autor, status=S.APPROVED)
    ma = _admin()
    ma.do_publish(_request(editor, with_messages=True), Article.objects.filter(pk=article.pk))
    article.refresh_from_db()
    assert article.status == S.PUBLISHED
    # La acción pasó por perform_transition → dejó rastro en la bitácora inmutable.
    assert article.transitions.filter(to_status=S.PUBLISHED).exists()


def test_publish_action_denied_for_author(autor, make_article):
    # El autor no es editor: la acción no debe publicar (guarda de perform_transition).
    article = make_article(owner=autor, status=S.APPROVED)
    ma = _admin()
    ma.do_publish(_request(autor, with_messages=True), Article.objects.filter(pk=article.pk))
    article.refresh_from_db()
    assert article.status == S.APPROVED  # sin cambios


def test_author_cannot_delete(autor, editor, make_article):
    ma = _admin()
    article = make_article(owner=autor, status=S.DRAFT)
    assert not ma.has_delete_permission(_request(autor), article)
    assert ma.has_delete_permission(_request(editor), article)
