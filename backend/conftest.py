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
def frozen_rate_limit_window(monkeypatch):
    """Una sola ventana de django-ratelimit durante toda la prueba. La biblioteca cuenta por
    ventanas fijas, del periodo de cada límite, y el fin de la ventana entra en la clave del
    contador: si las peticiones de una prueba cruzan un corte, la cuenta vuelve a cero y el
    límite no llega. Lo piden las pruebas que agotan un límite."""
    import time

    from django_ratelimit import core

    window = int(time.time()) + 3600
    monkeypatch.setattr(core, "_get_window", lambda value, period: window)
    return window


@pytest.fixture
def task_failures_stay_in_the_task():
    """Para las pruebas que hacen fallar una tarea a propósito: su excepción no llega a la
    prueba (la suite la propaga, config/settings_test.py), y el reintento corre como en el
    worker. Celery lee los ajustes una vez, con su prefijo: override_settings no le llega."""
    from config.celery import app

    app.conf.update(CELERY_TASK_EAGER_PROPAGATES=False)
    yield
    app.conf.update(CELERY_TASK_EAGER_PROPAGATES=True)


@pytest.fixture
def groups(db):
    """Los tres grupos CON sus permisos, como en producción.

    Son los de la matriz de roles (apps/people/roles.py), que el release reparte con
    `setup_groups`: las comprobaciones por rol del panel componen con los permisos de modelo
    de Django, así que un grupo vacío no se parece a ningún despliegue. Las pruebas que
    necesitan quitar un permiso lo quitan de forma explícita.
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
    """Las páginas legales, publicadas y con el texto que les dan las migraciones: las crea, si
    faltan, la misma función de `apps/content/legal.py` que usa la migración. Lo necesitan las
    pruebas que consultan esas páginas, porque una prueba transaccional previa (transaction=True)
    vacía la tabla, y con ella lo que sembraron las migraciones."""
    from apps.content import legal
    from apps.content.models import Page

    legal.create_pages(Page)


@pytest.fixture
def migrate(transactional_db):
    """Lleva una app a una de sus migraciones y devuelve los modelos históricos de ese momento:
    `old = migrate("content", "0013_permisos_de_revisar_y_publicar")` y después
    `old.get_model("content", "Article")`. Al terminar, la base vuelve a las últimas migraciones.

    Una migración de datos se prueba así: se va a la migración anterior, se crean con sus modelos
    las filas que la migración transforma, se migra y se comprueba qué quedó; si tiene vuelta, se
    vuelve a la anterior y se comprueba otra vez. La base es transaccional: cada migración se
    confirma por separado, como en un despliegue, y PostgreSQL no deja alterar una tabla que
    tiene comprobaciones de clave foránea pendientes en la misma transacción.
    """
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    def migrate_to(app, name):
        executor = MigrationExecutor(connection)
        executor.migrate([(app, name)])
        return executor.loader.project_state([(app, name)]).apps

    yield migrate_to
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


class _KeepSentryEvents:
    """Un transporte de Sentry que guarda los sobres en vez de mandarlos."""

    def __new__(cls):
        from sentry_sdk.transport import Transport

        class KeepEvents(Transport):
            def __init__(self):
                super().__init__()
                self.envelopes = []

            def capture_envelope(self, envelope):
                self.envelopes.append(envelope)

            def events(self):
                return [e for env in self.envelopes if (e := env.get_event()) is not None]

        return KeepEvents()


@pytest.fixture
def sentry_events():
    """Sentry arrancado como en producción (`init_sentry`), con un transporte que guarda los
    eventos: devuelve la función que los lista."""
    import sentry_sdk

    from config.sentry import init_sentry

    transport = _KeepSentryEvents()
    init_sentry("https://public@sentry.invalid/1", environment="test", transport=transport)
    yield transport.events
    sentry_sdk.get_client().close()
