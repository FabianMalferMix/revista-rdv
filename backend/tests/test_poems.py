import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content import workflow
from apps.content.models import (
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialStatus,
    EditorialTransition,
    PoemContributor,
    PublishStatus,
)
from apps.content.tasks import publish_due_items
from apps.people.models import Contributor
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db
S = EditorialStatus


# ── Flujo editorial compartido ───────────────────────────────


def test_poem_uses_editorial_workflow(editor, autor, make_poem):
    poem = make_poem(owner=autor, status=S.DRAFT)
    workflow.perform_transition(poem, "submit", autor)
    workflow.perform_transition(poem, "accept", editor)
    workflow.perform_transition(poem, "publish", editor)
    assert poem.status == S.PUBLISHED
    assert poem.published_at is not None


def test_poem_transitions_have_generic_audit_trail(editor, autor, make_poem, make_article):
    poem = make_poem(owner=autor, status=S.IN_REVIEW)
    article = make_article(owner=autor, status=S.IN_REVIEW)
    workflow.perform_transition(poem, "accept", editor, note="ok poema")
    workflow.perform_transition(article, "accept", editor, note="ok artículo")

    entry = poem.transitions.latest("created_at")
    assert entry.item == poem
    assert (entry.from_status, entry.to_status) == (S.IN_REVIEW, S.APPROVED)
    # El filtro por related_query_name distingue piezas del mismo id.
    assert EditorialTransition.objects.filter(poem=poem).count() == 1
    assert EditorialTransition.objects.filter(article=article).count() == 1


def test_author_cannot_publish_poem(autor, make_poem):
    from django.core.exceptions import PermissionDenied

    poem = make_poem(owner=autor, status=S.APPROVED)
    with pytest.raises(PermissionDenied):
        workflow.perform_transition(poem, "publish", autor)


def test_publish_due_items_covers_poems(make_poem):
    from datetime import timedelta

    poem = make_poem(status=S.SCHEDULED)
    poem.published_at = timezone.now() - timedelta(minutes=1)
    poem.save(update_fields=["published_at"])
    assert publish_due_items() >= 1
    poem.refresh_from_db()
    assert poem.status == S.PUBLISHED


# ── Vistas públicas ──────────────────────────────────────────


def _published_poem(make_poem, **kwargs):
    return make_poem(status=S.PUBLISHED, published_at=timezone.now(), **kwargs)


def test_poem_index_shows_published_hides_drafts(client, make_poem):
    _published_poem(make_poem, slug="pub", title="Poema Público")
    make_poem(slug="draft", title="Poema Borrador")
    resp = client.get(reverse("content:poem_index"))
    assert resp.status_code == 200
    assert b"Poema P\xc3\xbablico" in resp.content
    assert b"Poema Borrador" not in resp.content


def test_poem_detail_renders_prewrap_body(client, make_poem):
    poem = _published_poem(
        make_poem,
        slug="tipografia",
        title="Tipografía",
        epigraph="a quien lee",
        body="Verso uno\n    verso con sangría\n\nVerso final",
    )
    resp = client.get(reverse("content:poem_detail", args=[poem.slug]))
    assert resp.status_code == 200
    assert b'<div class="poem-body">' in resp.content
    # El cuerpo va escapado pero íntegro: saltos y sangrías intactos.
    assert "Verso uno\n    verso con sangría\n\nVerso final".encode() in resp.content
    assert b"a quien lee" in resp.content


def test_poem_detail_404_for_draft(client, make_poem):
    poem = make_poem(slug="oculto")
    assert client.get(reverse("content:poem_detail", args=[poem.slug])).status_code == 404


def test_poem_body_is_escaped(client, make_poem):
    poem = _published_poem(make_poem, slug="xss", body="<script>alert(1)</script>")
    resp = client.get(reverse("content:poem_detail", args=[poem.slug]))
    assert b"<script>alert(1)</script>" not in resp.content
    assert b"&lt;script&gt;" in resp.content


def test_collection_merges_articles_and_poems_by_position(client, make_article, make_poem):
    from tests.factories import publish as _publish

    collection = Collection.objects.create(
        slug="mixta", title="Colección Mixta", status=PublishStatus.PUBLISHED
    )
    article = _publish(make_article(slug="pieza-a", title="Artículo En Mixta"))
    poem = _published_poem(make_poem, slug="pieza-p", title="Poema En Mixta")
    CollectionArticle.objects.create(collection=collection, article=article, position=1)
    CollectionPoem.objects.create(collection=collection, poem=poem, position=0)

    resp = client.get(reverse("content:collection_detail", args=["mixta"]))
    assert resp.status_code == 200
    # El poema (position 0) aparece antes que el artículo (position 1).
    assert resp.content.index(b"Poema En Mixta") < resp.content.index(b"Art\xc3\xadculo En Mixta")


def test_member_profile_lists_poems(client, make_poem):
    member = Contributor.objects.create(slug="poeta-p", display_name="Poeta Perfil", is_member=True)
    poem = _published_poem(make_poem, slug="suyo", title="Poema Del Perfil")
    PoemContributor.objects.create(poem=poem, contributor=member)
    resp = client.get(reverse("people:member_detail", args=[member.slug]))
    assert b"Poema Del Perfil" in resp.content


def test_home_shows_featured_poem_only_if_published(client, make_poem):
    profile = SiteProfile.load()
    draft = make_poem(slug="dest-borrador", title="Destacado Borrador")
    profile.featured_poem = draft
    profile.save()
    assert b"Destacado Borrador" not in client.get(reverse("content:home")).content

    profile.featured_poem = _published_poem(make_poem, slug="dest-pub", title="Destacado Público")
    profile.save()
    assert b"Destacado P\xc3\xbablico" in client.get(reverse("content:home")).content
