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
from apps.media.models import MediaAsset
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
