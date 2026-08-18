import os

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


def _campos_con_almacen_en(raiz):
    """Campos de archivo cuyo almacén apunta a `raiz` (comparando la ruta ya resuelta)."""
    from django.apps import apps
    from django.db.models import FileField

    objetivo = os.path.abspath(raiz)
    for modelo in apps.get_models():
        for campo in modelo._meta.get_fields():
            if isinstance(campo, FileField) and getattr(campo, "storage", None) is not None:
                if os.path.abspath(getattr(campo.storage, "location", "")) == objetivo:
                    yield campo


def _reapuntar(almacen, destino):
    """Mueve un FileSystemStorage ya construido a otra ruta.

    `location` y `base_location` son `cached_property`: si no se vacían, el almacén sigue
    devolviendo la ruta que resolvió la primera vez.
    """
    almacen._location = destino
    almacen.__dict__.pop("base_location", None)
    almacen.__dict__.pop("location", None)


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    """MEDIA_ROOT y almacén PRIVADO temporales por test: los archivos subidos en los tests
    no contaminan las carpetas reales ni se acumulan como huérfanos entre corridas, y los
    nombres son predecibles (sin sufijo por colisión). Autouse global (hallazgo #11).

    El privado no se puede redirigir solo con `settings`: `Submission.file` declara
    `storage=private_storage`, un invocable que Django evalúa UNA vez al cargar el modelo,
    y el FileSystemStorage resultante se quedó con la ruta de entonces. Cambiar el ajuste
    después no lo mueve —por eso cada corrida de la suite dejaba un `m_*.txt` con
    «contenido-secreto» en el `private_media` de verdad—, así que hay que reapuntar la
    instancia y devolverla a su sitio al terminar.
    """
    settings.MEDIA_ROOT = str(tmp_path / "publico")
    privado_real = settings.PRIVATE_MEDIA_ROOT
    campos = list(_campos_con_almacen_en(privado_real))
    settings.PRIVATE_MEDIA_ROOT = str(tmp_path / "privado")
    for campo in campos:
        _reapuntar(campo.storage, settings.PRIVATE_MEDIA_ROOT)
    yield
    for campo in campos:
        _reapuntar(campo.storage, privado_real)


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
