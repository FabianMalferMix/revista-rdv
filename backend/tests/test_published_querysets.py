"""«Publicado» vive en los QuerySets de config/publishing.py, y en ningún otro sitio.

El canario: cada modelo publicable usa uno de esos QuerySets, y su `published()` deja fuera lo
oculto, en cada uno de sus estados, y dentro lo publicado, también desde una relación. Y el
vigilante: ningún filtro de lo publicado escrito a mano (`published=True`, `active=True` o
`status=…PUBLISHED`, también a través de una relación) fuera de una clase QuerySet.
"""

import ast
from datetime import timedelta
from itertools import count

import pytest
from django.apps import apps
from django.conf import settings
from django.db.models import BooleanField
from django.utils import timezone

from apps.agenda.models import Event
from apps.content.models import (
    Article,
    ArticleContributor,
    Collection,
    EditorialStatus,
    Page,
    Poem,
)
from apps.people.models import Contributor
from apps.showcase.models import Partner, PressMention
from config.publishing import PUBLISHED, EditorialQuerySet, PublishableQuerySet
from tests.factories import make_event, make_publication, make_recording

SERIAL = count()


def _slug():
    return f"canario-{next(SERIAL)}"


def _editorial(model, **fields):
    return model.objects.create(
        slug=_slug(), title="Canario", body="Un verso", published_at=timezone.now(), **fields
    )


# Cómo crear un objeto de cada modelo publicable en un estado dado (`True` es «publicado»).
BUILDERS = {
    "content.Article": lambda status: _editorial(Article, status=status),
    "content.Poem": lambda status: _editorial(Poem, status=status),
    "content.Collection": lambda status: Collection.objects.create(
        slug=_slug(), title="Canario", status=status
    ),
    "content.Page": lambda status: Page.objects.create(
        slug=_slug(), title="Canario", body="Texto", status=status
    ),
    "media.Recording": lambda shown: make_recording(slug=_slug(), published=shown),
    "agenda.Event": lambda shown: make_event(slug=_slug(), published=shown),
    "showcase.Publication": lambda shown: make_publication(slug=_slug(), published=shown),
    "showcase.PressMention": lambda shown: PressMention.objects.create(
        title="Canario", outlet="Gaceta de Prueba", published=shown
    ),
    "showcase.Partner": lambda shown: Partner.objects.create(name="Canario", active=shown),
}


def _uses_publishing_queryset(model):
    return isinstance(model._default_manager.all(), (EditorialQuerySet, PublishableQuerySet))


def _looks_publishable(model):
    """Una casilla `published`, o «publicado» entre los estados de `status`."""
    fields = {field.name: field for field in model._meta.concrete_fields}
    if isinstance(fields.get("published"), BooleanField):
        return True
    return PUBLISHED in dict(getattr(fields.get("status"), "choices", None) or ())


def test_every_publishable_model_has_its_queryset_and_its_canary():
    publishable = {model._meta.label for model in apps.get_models() if _looks_publishable(model)}
    with_queryset = {m._meta.label for m in apps.get_models() if _uses_publishing_queryset(m)}
    assert publishable <= with_queryset, (
        f"sin QuerySet de lo publicado: {publishable - with_queryset}"
    )
    # Los aliados se publican con `active`: tienen el QuerySet aunque no lo parezcan.
    assert with_queryset == set(BUILDERS), "cada modelo publicable necesita su canario aquí"


@pytest.mark.django_db
@pytest.mark.parametrize("label", BUILDERS)
def test_published_leaves_out_every_hidden_state(label):
    model = apps.get_model(label)
    if "status" in {field.name for field in model._meta.concrete_fields}:
        states = [value for value, _ in model._meta.get_field("status").choices]
        shown = BUILDERS[label](PUBLISHED)
        hidden = [BUILDERS[label](state) for state in states if state != PUBLISHED]
    else:
        shown = BUILDERS[label](True)
        hidden = [BUILDERS[label](False)]
    assert hidden, "el canario no tiene nada oculto que dejar fuera"
    assert list(model.objects.published()) == [shown]


@pytest.mark.django_db
def test_published_works_from_the_relations():
    member = Contributor.objects.create(
        slug="integrante", display_name="Integrante", is_member=True
    )
    shown = {}
    for status in (EditorialStatus.DRAFT, EditorialStatus.PUBLISHED):
        article = _editorial(Article, status=status)
        ArticleContributor.objects.create(article=article, contributor=member)
        event = make_event(
            slug=_slug(),
            published=status == PUBLISHED,
            starts_at=timezone.now() - timedelta(days=1),
        )
        event.participants.add(member)
        if status == PUBLISHED:
            shown = {"article": article, "event": event}
    assert list(member.articles.published()) == [shown["article"]]
    assert list(member.events.published()) == [shown["event"]]
    assert list(member.events.past()) == [shown["event"]]
    assert isinstance(Event.objects.all(), PublishableQuerySet)


# ── El vigilante ─────────────────────────────────────────────────────────────────────────────

FILTER_CALLS = {"filter", "exclude", "get", "Q", "get_object_or_404", "get_list_or_404"}


def _is_publishing_rule(keyword):
    """`published=True` o `active=True` (también `event__published=True`) y `status=…PUBLISHED`
    o `status="published"` (también `article__status=…`)."""
    parts = keyword.arg.split("__")
    value = keyword.value
    if {"published", "active"} & set(parts):
        return isinstance(value, ast.Constant) and value.value is True
    if "status" in parts:
        return (isinstance(value, ast.Attribute) and value.attr == "PUBLISHED") or (
            isinstance(value, ast.Constant) and value.value == PUBLISHED
        )
    return False


def hand_written_filters(source, name="<código>"):
    """Los filtros de lo publicado escritos fuera de una clase QuerySet, como `archivo:línea`."""
    found = []

    class Watcher(ast.NodeVisitor):
        inside_queryset = 0

        def visit_ClassDef(self, node):
            is_queryset = any(ast.unparse(base).endswith("QuerySet") for base in node.bases)
            self.inside_queryset += is_queryset
            self.generic_visit(node)
            self.inside_queryset -= is_queryset

        def visit_Call(self, node):
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if called in FILTER_CALLS and not self.inside_queryset:
                found.extend(
                    f"{name}:{node.lineno}: {keyword.arg}=…"
                    for keyword in node.keywords
                    if keyword.arg and _is_publishing_rule(keyword)
                )
            self.generic_visit(node)

    Watcher().visit(ast.parse(source))
    return found


def test_the_watcher_catches_a_filter_written_by_hand():
    """Control: el vigilante ve lo que tiene que ver y deja pasar los QuerySets."""
    source = """
def vista():
    Article.objects.filter(status=EditorialStatus.PUBLISHED)
    EventPhoto.objects.filter(event__published=True)
    Q(status="published")
    Partner.objects.filter(active=True)
    Submission.objects.filter(status=Submission.Status.RECEIVED)

class EventQuerySet(publishing.PublishableQuerySet):
    def upcoming(self):
        return self.filter(published=True)
"""
    assert [line.split(": ", 1)[1] for line in hand_written_filters(source)] == [
        "status=…",
        "event__published=…",
        "status=…",
        "active=…",
    ]


def test_no_publishing_filter_is_written_by_hand():
    root = settings.BASE_DIR
    sources = [
        path
        for folder in ("apps", "config")
        for path in sorted((root / folder).rglob("*.py"))
        if "migrations" not in path.parts
    ]
    assert len(sources) > 50, "no se encontró el código de las apps"
    found = [
        hit
        for path in sources
        for hit in hand_written_filters(path.read_text(encoding="utf-8"), path.relative_to(root))
    ]
    assert found == [], "filtros de lo publicado escritos a mano (usa .published()):\n" + "\n".join(
        found
    )
