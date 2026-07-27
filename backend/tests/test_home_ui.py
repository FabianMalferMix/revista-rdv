"""Portada reordenada y archivo de textos (Lote UI-1)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db


def _pub(make_article, **kw):
    return make_article(status=EditorialStatus.PUBLISHED, published_at=timezone.now(), **kw)


def test_home_caps_articles_and_links_to_archive(client, make_article):
    for i in range(8):
        _pub(make_article, slug=f"t{i}", title=f"Texto {i}")
    resp = client.get(reverse("content:home"))
    assert resp.status_code == 200
    # Portada curada: como mucho 5 tarjetas de artículo (el resto vive en el archivo).
    assert resp.content.count(b"article-card") <= 5
    assert reverse("content:text_archive").encode() in resp.content


def test_text_archive_paginates_full_list(client, make_article):
    for i in range(15):
        _pub(make_article, slug=f"a{i}")
    resp = client.get(reverse("content:text_archive"))
    assert resp.status_code == 200
    page = resp.context["articles"]
    assert page.paginator.count == 15
    assert len(page.object_list) == 12
    page2 = client.get(reverse("content:text_archive") + "?page=2").context["articles"]
    assert len(page2.object_list) == 3


def test_home_shows_single_featured_recording_over_poem(client, make_poem):
    profile = SiteProfile.load()
    profile.featured_poem = make_poem(
        slug="p-dest",
        title="Poema Destacado",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    profile.featured_recording = Recording.objects.create(
        slug="r-dest",
        title="Registro Destacado",
        embed_url="https://youtu.be/xyz123ab",
        published=True,
    )
    profile.save()
    resp = client.get(reverse("content:home"))
    # Con ambos definidos, el registro manda: un solo destacado, sin apilar.
    assert b"Registro Destacado" in resp.content
    assert b"Poema Destacado" not in resp.content


def test_home_members_appear_before_texts(client, make_article):
    Contributor.objects.create(slug="m1", display_name="Integrante Uno", is_member=True)
    _pub(make_article, slug="tx", title="Texto Portada")
    content = client.get(reverse("content:home")).content
    assert content.index(b"Integrante Uno") < content.index(b"Texto Portada")


def test_home_hero_has_manifesto_and_stats(client):
    profile = SiteProfile.load()
    profile.tagline = "Poesía en voz alta."
    profile.manifesto = "Somos un colectivo que difunde la obra de sus integrantes."
    profile.founded_year = 2019
    profile.save()
    resp = client.get(reverse("content:home"))
    assert b"hero-manifesto" in resp.content
    assert b"hero-stats" in resp.content
    assert b"Poes\xc3\xada en voz alta." in resp.content
