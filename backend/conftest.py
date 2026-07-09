import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


@pytest.fixture
def groups(db):
    return {
        name: Group.objects.get_or_create(name=name)[0] for name in ["admin", "editor", "autor"]
    }


@pytest.fixture
def editor(db, groups):
    user = get_user_model().objects.create_user("editor_test", password="pw", is_staff=True)
    user.groups.add(groups["editor"])
    return user


@pytest.fixture
def autor(db, groups):
    user = get_user_model().objects.create_user("autor_test", password="pw", is_staff=True)
    user.groups.add(groups["autor"])
    return user


@pytest.fixture
def make_article(db):
    """Fábrica de artículos. Uso: make_article(owner=autor, status=..., title=...)."""
    from apps.content.models import Article, ArticleStatus

    def _make(**kwargs):
        n = Article.objects.count()
        defaults = {
            "slug": f"articulo-{n}",
            "title": "Título de prueba",
            "body": "palabra " * 250,
            "status": ArticleStatus.DRAFT,
        }
        defaults.update(kwargs)
        return Article.objects.create(**defaults)

    return _make
