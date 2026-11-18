"""Los datos estructurados (JSON-LD), la dirección canónica y la descripción de cada página."""

import json
import re
from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Event
from apps.content.models import EditorialStatus
from tests.factories import make_article, make_published_article

pytestmark = pytest.mark.django_db


def _jsonld(content):
    blocks = re.findall(rb'<script type="application/ld\+json"[^>]*>(.*?)</script>', content, re.S)
    return [json.loads(b.decode()) for b in blocks]


def test_home_has_valid_organization_jsonld(client):
    blocks = _jsonld(client.get(reverse("site:home")).content)
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


# ── Canonical / og:url sin query string ─────────────────────────────────────


def test_canonical_and_og_url_strip_tracking_query(client, settings):
    """El canonical y og:url no arrastran query strings (utm_*, q, …) que
    ensuciarían la señal de canonicalización, y salen del origen fijo del sitio."""
    settings.SITE_URL = "https://revista.example.org"
    head = client.get("/?q=zzz&utm_source=news").content.decode().split("</head>")[0]
    assert '<link rel="canonical" href="https://revista.example.org/">' in head
    assert '<meta property="og:url" content="https://revista.example.org/">' in head
    assert "utm_source" not in head


def _canonical(client, url):
    return BeautifulSoup(client.get(url).content, "html.parser").select_one(
        'head link[rel="canonical"]'
    )["href"]


def test_the_canonical_names_the_page_that_was_served(client, settings):
    """En un listado paginado cada página es un recurso: la canónica de la segunda lleva
    `?page=2`. La de la primera no lo lleva, tampoco pedida con `?page=1`, y una página que no
    pagina no lo copia de la URL."""
    settings.SITE_URL = "https://revista.example.org"
    for _ in range(13):
        make_published_article()
    archive = reverse("content:text_archive")
    assert _canonical(client, f"{archive}?page=2") == f"https://revista.example.org{archive}?page=2"
    assert _canonical(client, f"{archive}?page=1") == f"https://revista.example.org{archive}"
    assert _canonical(client, archive) == f"https://revista.example.org{archive}"
    assert _canonical(client, "/?page=2") == "https://revista.example.org/"


# ── Fallback de meta description y endDate de Event ──────────────────────────


def test_article_meta_description_falls_back_to_title(client):
    """Sin seo_description ni subtitle, la meta description cae al título (no vacía)."""
    art = make_article(status=EditorialStatus.PUBLISHED, slug="sin-desc", title="Solo Título")
    html = client.get(reverse("content:article_detail", args=[art.slug])).content.decode()
    assert '<meta name="description" content="Solo Título">' in html


def test_event_jsonld_includes_enddate_when_present(client):
    """El JSON-LD de Event declara endDate cuando el evento tiene hora de fin."""
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
    assert event_ld["name"] == "Sin Fin" and event_ld["startDate"]  # control
    assert "endDate" not in event_ld
