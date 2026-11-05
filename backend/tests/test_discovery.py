"""Superficie de descubrimiento/sindicación: sitemap.xml y RSS de artículos.

Cubre los hallazgos #05 (sitemap y RSS sin ninguna prueba) y #12 (el sitemap
omitía la portada y las páginas índice). Una regresión silenciosa —reverse mal
escrito, modelo sin get_absolute_url, cambio de esquema XML— rompería estas
páginas en producción sin que la suite lo detectara.

La validación de contrato usa la stdlib (minidom): comprueba que el XML está bien
formado y que las etiquetas clave existen, sin añadir dependencias (feedparser).
"""

import xml.dom.minidom as minidom
from datetime import UTC, datetime

import pytest
from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Event
from apps.content.models import Article, EditorialStatus, Poem
from apps.content.sitemaps import SITEMAPS
from apps.media.models import Recording
from apps.showcase.models import Publication
from config.models import TimestampedModel
from tests.factories import (
    make_article,
    make_event,
    make_poem,
    make_publication,
    make_published_article,
    make_published_poem,
    make_recording,
)

pytestmark = pytest.mark.django_db


# ── sitemap.xml ──────────────────────────────────────────────


def test_sitemap_ok_and_valid_xml(client):
    make_article(status=EditorialStatus.PUBLISHED, slug="pub-x", title="Publicado X")
    resp = client.get(reverse("sitemap"))
    assert resp.status_code == 200
    dom = minidom.parseString(resp.content)  # XML bien formado (lanza si no)
    assert dom.getElementsByTagName("urlset"), "falta <urlset>"
    assert dom.getElementsByTagName("url"), "el sitemap no tiene ninguna <url>"


def test_sitemap_lists_published_article_hides_draft(client):
    pub = make_article(status=EditorialStatus.PUBLISHED, slug="art-pub")
    draft = make_article(status=EditorialStatus.DRAFT, slug="art-draft")
    content = client.get(reverse("sitemap")).content.decode()
    assert reverse("content:article_detail", args=[pub.slug]) in content
    assert reverse("content:article_detail", args=[draft.slug]) not in content


def test_sitemap_includes_static_landing_pages(client):
    """El sitemap incluye la portada y los índices; antes los omitía (#12)."""
    content = client.get(reverse("sitemap")).content.decode()
    for name in [
        "content:home",
        "content:poem_index",
        "people:member_index",
        "agenda:agenda",
        "showcase:publication_index",
        "media:recording_index",
    ]:
        assert reverse(name) in content, f"falta {name} en el sitemap"


def test_every_sitemap_section_builds_urls_without_error():
    """Con datos sembrados, cada sección construye sus <url> (items + location +
    lastmod) sin lanzar: evita romper el sitemap entero por un filtro/campo/reverse
    mal escrito en cualquiera de las 13 secciones."""
    from django.contrib.sites.requests import RequestSite
    from django.test import RequestFactory

    make_article(status=EditorialStatus.PUBLISHED, slug="seed-art")
    make_poem(status=EditorialStatus.PUBLISHED, slug="seed-poem")
    site = RequestSite(RequestFactory().get("/"))
    for cls in SITEMAPS.values():
        list(cls().get_urls(site=site))  # no debe lanzar en ninguna sección


# Las fichas cuyo modelo guarda cuándo se editó, con cómo crear una publicada.
EDITED_PIECES = {
    Article: make_published_article,
    Poem: make_published_poem,
    Event: make_event,
    Publication: make_publication,
    Recording: make_recording,
}


def _lastmod(client, piece):
    """La fecha de la última edición que el sitemap anuncia para la ficha de la pieza."""
    dom = minidom.parseString(client.get(reverse("sitemap")).content)
    for url in dom.getElementsByTagName("url"):
        if url.getElementsByTagName("loc")[0].firstChild.data.endswith(piece.get_absolute_url()):
            (lastmod,) = url.getElementsByTagName("lastmod")
            return lastmod.firstChild.data
    raise AssertionError(f"{piece.get_absolute_url()} no está en el sitemap")


def test_every_sitemap_section_of_pieces_that_keep_their_last_edit_is_checked_below():
    items = [cls().items() for cls in SITEMAPS.values()]
    edited = {
        rows.model
        for rows in items
        if isinstance(rows, QuerySet) and issubclass(rows.model, TimestampedModel)
    }
    assert edited == set(EDITED_PIECES)


@pytest.mark.parametrize("model", list(EDITED_PIECES), ids=lambda model: model.__name__)
def test_the_sitemap_says_when_each_page_was_last_edited(client, model):
    """Un buscador vuelve a leer una ficha cuando el sitemap le dice que cambió."""
    piece = EDITED_PIECES[model]()
    model.objects.filter(pk=piece.pk).update(updated_at=datetime(2026, 3, 14, 12, tzinfo=UTC))
    assert _lastmod(client, piece) == "2026-03-14"
    piece.refresh_from_db()
    piece.save()  # una edición en el panel
    assert _lastmod(client, piece) == timezone.localdate().isoformat()


# ── RSS de artículos (/feed/) ────────────────────────────────


def test_articles_feed_ok_and_valid_xml(client):
    make_article(
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        slug="feed-x",
        title="Artículo En Feed",
    )
    resp = client.get(reverse("feed"))
    assert resp.status_code == 200
    dom = minidom.parseString(resp.content)  # XML bien formado
    assert dom.getElementsByTagName("rss"), "no es un RSS válido"
    assert dom.getElementsByTagName("item"), "el feed no tiene ningún <item>"
    assert "Artículo En Feed" in resp.content.decode()


def test_articles_feed_lists_published_hides_draft(client):
    pub = make_article(
        status=EditorialStatus.PUBLISHED, published_at=timezone.now(), slug="feed-pub"
    )
    make_article(status=EditorialStatus.DRAFT, slug="feed-draft")
    content = client.get(reverse("feed")).content.decode()
    assert reverse("content:article_detail", args=[pub.slug]) in content
    assert reverse("content:article_detail", args=["feed-draft"]) not in content


# ── Escala: cap de ítems del feed y sitemap sin truncado silencioso ──────────


def test_articles_feed_caps_at_twenty_items(client):
    """El RSS de artículos limita a 20 ítems (items()[:20]), aunque haya más."""
    import xml.dom.minidom as minidom

    for i in range(25):
        make_article(status=EditorialStatus.PUBLISHED, published_at=timezone.now(), slug=f"cap-{i}")
    dom = minidom.parseString(client.get(reverse("feed")).content)
    assert len(dom.getElementsByTagName("item")) == 20


def test_sitemap_lists_all_items_without_truncation(client):
    """El sitemap emite todas las piezas publicadas (sin truncado silencioso) cuando
    su número supera el de una página típica pero no el límite de 50k de Django."""
    slugs = []
    for i in range(55):
        art = make_article(status=EditorialStatus.PUBLISHED, slug=f"volumen-{i}")
        slugs.append(art.slug)
    content = client.get(reverse("sitemap")).content.decode()
    assert all(reverse("content:article_detail", args=[s]) in content for s in slugs)
