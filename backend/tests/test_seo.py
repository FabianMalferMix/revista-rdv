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


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


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
