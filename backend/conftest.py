import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


@pytest.fixture(autouse=True)
def _clear_cache():
    """Caché limpia por test: evita que los contadores de django-ratelimit (LocMem,
    persistente en el proceso) se filtren entre tests."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    """MEDIA_ROOT temporal por test: los archivos subidos en los tests no contaminan
    el MEDIA_ROOT real ni se acumulan como huérfanos entre corridas, y los nombres son
    predecibles (sin sufijo por colisión). Autouse global (hallazgo #11)."""
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def groups(db):
    """Los tres grupos CON sus permisos, como en producción.

    Antes se creaban vacíos, así que los tests del admin trabajaban con un editor sin
    `content.change_article`: una situación que no se da en ningún despliegue, porque el
    entrypoint ejecuta `setup_groups`. La diferencia dejó de ser inocua al hacer que las
    comprobaciones por rol COMPONGAN con los permisos de modelo de Django (S-20).
    """
    from django.core.management import call_command

    call_command("setup_groups", verbosity=0)
    return {name: Group.objects.get(name=name) for name in ["admin", "editor", "autor"]}


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
def legal_pages(db):
    """Re-crea las páginas legales que siembran las migraciones de datos (0007 y la
    actualización a Ley 21.719 de 0010), reutilizando sus funciones RunPython. Lo
    necesitan los tests que consultan esas páginas directamente, porque un test
    transaccional previo (transaction=True) pudo vaciar la tabla."""
    import importlib

    from django.apps import apps as django_apps

    for module, func in (
        ("apps.content.migrations.0007_legal_pages", "create_pages"),
        ("apps.content.migrations.0010_privacy_ley_21719", "update_privacy"),
    ):
        getattr(importlib.import_module(module), func)(django_apps, None)


@pytest.fixture
def make_article(db):
    """Fábrica de artículos. Uso: make_article(owner=autor, status=..., title=...)."""
    from apps.content.models import Article, EditorialStatus

    def _make(**kwargs):
        n = Article.objects.count()
        defaults = {
            "slug": f"articulo-{n}",
            "title": "Título de prueba",
            "body": "palabra " * 250,
            "status": EditorialStatus.DRAFT,
        }
        defaults.update(kwargs)
        return Article.objects.create(**defaults)

    return _make


@pytest.fixture
def make_poem(db):
    """Fábrica de poemas. Uso: make_poem(owner=autor, status=..., title=...)."""
    from apps.content.models import EditorialStatus, Poem

    def _make(**kwargs):
        n = Poem.objects.count()
        defaults = {
            "slug": f"poema-{n}",
            "title": "Poema de prueba",
            "body": "Verso uno\n    verso con sangría\n\nVerso final",
            "status": EditorialStatus.DRAFT,
        }
        defaults.update(kwargs)
        return Poem.objects.create(**defaults)

    return _make
