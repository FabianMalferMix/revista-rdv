"""Datos estructurados (JSON-LD) y og:image por defecto — Lote F3-6."""

import json
import re
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.agenda.models import Event
from apps.content.models import EditorialStatus
from apps.media.models import MediaAsset, Recording
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db


def _jsonld(content):
    blocks = re.findall(rb'<script type="application/ld\+json"[^>]*>(.*?)</script>', content, re.S)
    return [json.loads(b.decode()) for b in blocks]


def _asset():
    buf = BytesIO()
    Image.new("RGB", (1200, 630), (10, 10, 10)).save(buf, format="JPEG")
    return MediaAsset.objects.create(
        file=SimpleUploadedFile("og.jpg", buf.getvalue(), content_type="image/jpeg"),
        alt_text="tarjeta social",
    )


def test_home_has_valid_organization_jsonld(client):
    blocks = _jsonld(client.get(reverse("content:home")).content)
    org = [d for d in blocks if d["@type"] == "Organization"]
    assert org, "la portada debe emitir JSON-LD de Organization"
    assert org[0]["name"]
    assert org[0]["url"].endswith("/")


def test_event_detail_has_valid_event_jsonld(client):
    ev = Event.objects.create(
        slug="recital-seo",
        title="Recital SEO",
        published=True,
        starts_at=timezone.now() + timedelta(days=3),
        venue_name="Sala Norte",
        city="Santiago",
    )
    blocks = _jsonld(client.get(reverse("agenda:event_detail", args=[ev.slug])).content)
    event = [d for d in blocks if d["@type"] == "Event"]
    assert event, "el detalle de evento debe emitir JSON-LD de Event"
    assert event[0]["name"] == "Recital SEO"
    assert event[0]["location"]["@type"] == "Place"
    assert event[0]["startDate"]


def test_default_og_image_falls_back_to_siteprofile(client):
    url = reverse("content:home")
    # Sin og_image no hay imagen social de página.
    assert b'property="og:image"' not in client.get(url).content
    profile = SiteProfile.load()
    profile.og_image = _asset()
    profile.save()
    assert b'property="og:image"' in client.get(url).content


def test_poem_detail_falls_back_to_site_og_image(client, make_poem):
    poem = make_poem(slug="poema-og", status=EditorialStatus.PUBLISHED)
    poem.published_at = timezone.now()
    poem.save()
    profile = SiteProfile.load()
    profile.og_image = _asset()
    profile.save()
    resp = client.get(reverse("content:poem_detail", args=[poem.slug]))
    assert resp.status_code == 200
    assert b'property="og:image"' in resp.content  # cae a la imagen del sitio
    assert b"summary_large_image" in resp.content


def test_recording_detail_falls_back_to_site_og_image(client):
    rec = Recording.objects.create(
        slug="reg-og",
        title="Registro OG",
        embed_url="https://youtu.be/abc123",
        published=True,
        published_at=timezone.now(),
    )
    profile = SiteProfile.load()
    profile.og_image = _asset()
    profile.save()
    resp = client.get(reverse("media:recording_detail", args=[rec.slug]))
    assert resp.status_code == 200
    assert b'property="og:image"' in resp.content


# ── Canonical / og:url sin query string (hallazgo #06) ──────────────────────


def test_canonical_and_og_url_strip_tracking_query(client):
    """El canonical y og:url no arrastran query strings (utm_*, q, …) que
    ensuciarían la señal de canonicalización."""
    head = client.get("/?q=zzz&utm_source=news").content.decode().split("</head>")[0]
    assert '<link rel="canonical" href="http://testserver/">' in head
    assert '<meta property="og:url" content="http://testserver/">' in head
    assert "utm_source" not in head


def test_canonical_preserves_pagination(client):
    """En listados paginados sí se preserva ?page= (cada página es un recurso)."""
    head = client.get("/?page=2").content.decode().split("</head>")[0]
    assert '<link rel="canonical" href="http://testserver/?page=2">' in head


# ── image en JSON-LD, fallback de meta description, endDate de Event ─────────


def test_article_jsonld_includes_image_when_og_available(client, make_article):
    """El JSON-LD de Article incluye "image" cuando hay portada o og_image del sitio (#15)."""
    profile = SiteProfile.load()
    profile.og_image = _asset()
    profile.save()
    art = make_article(status=EditorialStatus.PUBLISHED, slug="art-img", title="Con Imagen")
    data = _jsonld(client.get(reverse("content:article_detail", args=[art.slug])).content)
    article_ld = next(d for d in data if d.get("@type") == "Article")
    assert article_ld.get("image", "").startswith("http")


def test_article_meta_description_falls_back_to_title(client, make_article):
    """Sin seo_description ni subtitle, la meta description cae al título (no vacía, #30)."""
    art = make_article(status=EditorialStatus.PUBLISHED, slug="sin-desc", title="Solo Título")
    html = client.get(reverse("content:article_detail", args=[art.slug])).content.decode()
    assert '<meta name="description" content="Solo Título">' in html


def test_event_jsonld_includes_enddate_when_present(client):
    """El JSON-LD de Event declara endDate cuando el evento tiene hora de fin (#31)."""
    start = timezone.now() + timedelta(days=5)
    ev = Event.objects.create(
        slug="ev-end",
        title="Evento Con Fin",
        starts_at=start,
        ends_at=start + timedelta(hours=2),
        published=True,
    )
    data = _jsonld(client.get(reverse("agenda:event_detail", args=[ev.slug])).content)
    event_ld = next(d for d in data if d.get("@type") == "Event")
    assert "endDate" in event_ld


def test_event_jsonld_omits_enddate_when_absent(client):
    ev = Event.objects.create(
        slug="ev-noend",
        title="Sin Fin",
        starts_at=timezone.now() + timedelta(days=5),
        published=True,
    )
    data = _jsonld(client.get(reverse("agenda:event_detail", args=[ev.slug])).content)
    event_ld = next(d for d in data if d.get("@type") == "Event")
    assert "endDate" not in event_ld
