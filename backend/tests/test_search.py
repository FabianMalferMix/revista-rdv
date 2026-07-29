"""Vista de búsqueda FTS en vivo (htmx): artículos y poemas — Lotes F2-6 / F3-1."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import Article, EditorialStatus, Poem

pytestmark = pytest.mark.django_db
S = EditorialStatus


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


def test_search_finds_published_poem(client, make_poem):
    _publish(make_poem(slug="poema-fts", title="Elegía del faro", body="luz que gira en la niebla"))
    resp = client.get(reverse("content:search"), {"q": "faro"})
    assert resp.status_code == 200
    assert "Elegía del faro".encode() in resp.content
    assert b"Poema" in resp.content  # kicker de tipo
    assert reverse("content:poem_detail", args=["poema-fts"]).encode() in resp.content


def test_search_excludes_draft_poems(client, make_poem):
    make_poem(slug="poema-draft", title="Poema oculto del abismo", body="secretos", status=S.DRAFT)
    resp = client.get(reverse("content:search"), {"q": "abismo"})
    assert b"Poema oculto" not in resp.content
    assert b"Sin resultados" in resp.content


def test_poem_search_vector_tracks_bulk_update(client, make_poem):
    # QuerySet.update NO pasa por save(): con el trigger, el vector igual se refresca
    # (el enfoque previo, que recalculaba solo en save(), dejaba el vector obsoleto).
    poem = _publish(make_poem(slug="poema-bulk", title="Título inicial", body="palabra vieja"))
    Poem.objects.filter(pk=poem.pk).update(body="hipogrifo violento")
    resp = client.get(reverse("content:search"), {"q": "hipogrifo"})
    assert "Título inicial".encode() in resp.content


def test_article_search_vector_tracks_bulk_update(client, make_article):
    art = _publish(make_article(slug="art-bulk", title="Reseña bulk", body="palabra vieja"))
    Article.objects.filter(pk=art.pk).update(body="quetzalcoatl emplumado")
    resp = client.get(reverse("content:search"), {"q": "quetzalcoatl"})
    assert b"Rese\xc3\xb1a bulk" in resp.content


# ── Degradación sin JavaScript (hallazgo #09) ───────────────────────────────


def test_search_without_js_returns_full_page(client, make_article):
    """Una navegación normal (sin htmx) recibe la página completa con layout, no un
    fragmento suelto: la búsqueda funciona sin JavaScript."""
    _publish(make_article(slug="fts-page", title="Reseña navegable"))
    html = client.get(reverse("content:search"), {"q": "navegable"}).content.decode()
    assert "<h1>Búsqueda</h1>" in html  # cabecera de la página completa
    assert "</html>" in html  # layout de base presente
    assert "Reseña navegable" in html  # el resultado aparece


def test_search_with_htmx_returns_fragment_only(client, make_article):
    """Con htmx (HX-Request) se devuelve solo el fragmento, sin el layout."""
    _publish(make_article(slug="fts-frag", title="Reseña fragmento"))
    resp = client.get(reverse("content:search"), {"q": "fragmento"}, headers={"HX-Request": "true"})
    html = resp.content.decode()
    assert "Reseña fragmento" in html
    assert "<h1>Búsqueda</h1>" not in html  # sin cabecera de página
    assert "</html>" not in html  # sin layout
