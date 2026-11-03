"""Lo que hay que acordarse de registrar, comprobado contra el código.

Un campo de archivo nuevo borra su archivo con la fila, una ficha nueva se anuncia en el
sitemap (o dice por qué no), un modelo nuevo decide si viaja a la copia de desarrollo, una tarea
de beat apunta a una tarea que existe y una ruta nueva tiene categoría. Si alguien añade una de
esas cosas sin decidir, la suite falla.
"""

import pytest
from django.apps import apps
from django.conf import settings
from django.db.models import FileField
from django.db.models.signals import post_delete, pre_save
from django.dispatch.dispatcher import _make_id
from django.urls import URLResolver, get_resolver, resolve, reverse

from apps.content.management.commands.datos_de_desarrollo import MODELOS, NOT_EXPORTED
from apps.content.models import Article
from apps.content.sitemaps import EXCLUDED_FROM_SITEMAP, SITEMAPS, StaticViewSitemap
from apps.media.filecleanup import EXEMPT
from apps.people.models import Contributor
from config.celery import app as celery_app
from tests.factories import publish

INDEX, ENTITY, UTILITY = "índice", "ficha", "utilidad"
# Toda ruta con nombre fuera del panel, en su categoría. Los índices son los del sitemap; las
# fichas, una por pieza; el resto no se anuncia (archivos, feeds, formularios, salud del sitio).
ROUTES = {
    "content:home": INDEX,
    "content:text_archive": INDEX,
    "content:poem_index": INDEX,
    "content:collection_index": INDEX,
    "people:member_index": INDEX,
    "agenda:agenda": INDEX,
    "agenda:trayectoria": INDEX,
    "agenda:gallery": INDEX,
    "media:recording_index": INDEX,
    "showcase:publication_index": INDEX,
    "showcase:press_index": INDEX,
    "showcase:partner_index": INDEX,
    "showcase:dossier": INDEX,
    "content:article_detail": ENTITY,
    "content:poem_detail": ENTITY,
    "content:section_detail": ENTITY,
    "content:tag_detail": ENTITY,
    "content:contributor_detail": ENTITY,
    "content:collection_detail": ENTITY,
    "content:page_detail": ENTITY,
    "people:member_detail": ENTITY,
    "media:recording_detail": ENTITY,
    "agenda:event_detail": ENTITY,
    "showcase:publication_detail": ENTITY,
    "reviews:work_detail": ENTITY,
    "reviews:publisher_detail": ENTITY,
    "reviews:bookauthor_detail": ENTITY,
    "healthz": UTILITY,
    "readyz": UTILITY,
    "sitemap": UTILITY,
    "feed": UTILITY,
    "recordings_feed": UTILITY,
    "robots": UTILITY,
    "favicon": UTILITY,
    "media:recording_file": UTILITY,
    "showcase:publication_pdf": UTILITY,
    "submissions:file": UTILITY,
    "community:subscribe": UTILITY,
    "community:confirm": UTILITY,
    "community:unsubscribe": UTILITY,
    "submissions:submit": UTILITY,
    "submissions:submit_thanks": UTILITY,
    "content:search": UTILITY,
}


def _project_models():
    return [m for m in apps.get_models() if m.__module__.startswith("apps.")]


def _named_routes():
    names = []

    def walk(patterns, namespace):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                if pattern.app_name != "admin":
                    walk(
                        pattern.url_patterns, ":".join(filter(None, [namespace, pattern.namespace]))
                    )
            elif pattern.name:
                names.append(f"{namespace}:{pattern.name}" if namespace else pattern.name)

    walk(get_resolver().url_patterns, None)
    return names


def _sitemap_routes():
    """La ficha que lista cada sección del sitemap: la de la dirección de una pieza cualquiera."""
    routes = set()
    for section in SITEMAPS.values():
        sitemap = section()
        items = sitemap.items()
        if isinstance(items, list):
            continue
        routes.add(resolve(sitemap.location(items.model(slug="x"))).view_name)
    return routes


def test_every_file_field_deletes_its_file_with_the_row():
    fields = [
        (model, field.name)
        for model in _project_models()
        for field in model._meta.fields
        if isinstance(field, FileField)
    ]
    assert len(fields) >= 5
    for model, name in fields:
        label = f"{model._meta.label_lower}:{name}"
        if f"{model._meta.label}.{name}" in EXEMPT:
            continue
        for signal, kind in ((post_delete, "delete"), (pre_save, "replace")):
            key = (f"filecleanup:{kind}:{label}", _make_id(model))
            assert key in {receiver[0] for receiver in signal.receivers}, f"{label} ({kind})"
    declared = {f"{model._meta.label}.{name}" for model, name in fields}
    assert set(EXEMPT) <= declared, "an exemption names a field that does not exist"


def test_every_named_route_has_a_category():
    assert sorted(_named_routes()) == sorted(ROUTES)


def test_the_indexes_are_the_static_part_of_the_sitemap():
    assert {r for r, kind in ROUTES.items() if kind == INDEX} == set(StaticViewSitemap._views)


def test_every_entity_page_is_in_the_sitemap_or_says_why_not():
    entities = {route for route, kind in ROUTES.items() if kind == ENTITY}
    listed = _sitemap_routes()
    assert entities - set(EXCLUDED_FROM_SITEMAP) == listed
    assert set(EXCLUDED_FROM_SITEMAP) <= entities and not set(EXCLUDED_FROM_SITEMAP) & listed
    assert all(reason.strip() for reason in EXCLUDED_FROM_SITEMAP.values())


@pytest.mark.django_db
def test_a_collaborator_with_published_work_is_in_the_sitemap(client):
    signed = Contributor.objects.create(slug="firma-invitada", display_name="Firma invitada")
    Contributor.objects.create(slug="sin-obra", display_name="Sin obra")
    article = Article.objects.create(slug="un-texto", title="Un texto", body="<p>x</p>")
    article.authors.add(signed)
    publish(article)
    xml = client.get(reverse("sitemap")).content.decode()
    assert reverse("content:contributor_detail", args=["firma-invitada"]) in xml
    assert reverse("content:article_detail", args=["un-texto"]) in xml
    assert "sin-obra" not in xml
    assert client.get(reverse("content:contributor_detail", args=["sin-obra"])).status_code == 404


def test_every_model_says_whether_it_travels_to_the_development_copy():
    labels = {model._meta.label for model in _project_models()}
    assert labels == set(MODELOS) | set(NOT_EXPORTED)
    assert not set(MODELOS) & set(NOT_EXPORTED)
    assert all(reason.strip() for reason in NOT_EXPORTED.values())


def test_every_beat_entry_names_a_registered_task():
    celery_app.loader.import_default_modules()
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert schedule
    for name, entry in schedule.items():
        assert entry["task"] in celery_app.tasks, name
