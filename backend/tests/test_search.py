"""Vista de búsqueda FTS en vivo (htmx) — Lote F2-6."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus

pytestmark = pytest.mark.django_db


def _publish(article):
    article.status = EditorialStatus.PUBLISHED
    article.published_at = timezone.now()
    article.save()
    return article


def test_search_finds_published_match(client, make_article):
    _publish(make_article(slug="fts-1", title="Reseña de poesía chilena"))
    resp = client.get(reverse("content:search"), {"q": "poesía"})
    assert resp.status_code == 200
    assert "Reseña de poesía chilena".encode() in resp.content
    assert b"search-list" in resp.content


def test_search_excludes_drafts(client, make_article):
    make_article(slug="fts-draft", title="Borrador secreto de poesía", status=EditorialStatus.DRAFT)
    resp = client.get(reverse("content:search"), {"q": "secreto"})
    assert b"Borrador secreto" not in resp.content
    assert b"Sin resultados" in resp.content


def test_search_empty_query_renders_nothing(client, make_article):
    _publish(make_article(slug="fts-2", title="Algo publicado"))
    resp = client.get(reverse("content:search"), {"q": ""})
    assert resp.status_code == 200
    assert b"Algo publicado" not in resp.content
    assert b"search-list" not in resp.content  # ni lista ni estado vacío


def test_search_no_match_shows_empty_state(client, make_article):
    _publish(make_article(slug="fts-3", title="Reseña de narrativa urbana"))
    resp = client.get(reverse("content:search"), {"q": "zxqwvk"})
    assert b"Sin resultados" in resp.content
    assert b"search-list" not in resp.content
