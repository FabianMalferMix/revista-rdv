"""Pruebas de la arquitectura de información final (Lote H)."""

import re

import pytest
from django.urls import reverse

from apps.community.models import NewsletterSubscriber
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db


def _nav(content):
    return re.search(rb"<nav[^>]*>.*?</nav>", content, re.S).group(0)


def test_nav_curated_for_managers(client):
    resp = client.get(reverse("content:home"))
    nav = _nav(resp.content)
    for expected in [b"Poemas", b"Integrantes", b"Trayectoria", b"Prensa", b"Dossier"]:
        assert expected in nav
    # Lo editorial fino y las convocatorias salen de la nav principal (van al pie).
    assert reverse("submissions:submit").encode() not in nav
    assert reverse("content:collection_index").encode() not in nav


def test_footer_keeps_secondary_links(client):
    resp = client.get(reverse("content:home"))
    footer = resp.content.split(b"site-foot")[1]
    assert reverse("submissions:submit").encode() in footer
    assert reverse("content:collection_index").encode() in footer
    assert reverse("recordings_feed").encode() in footer


def test_seo_defaults_use_site_profile(client):
    profile = SiteProfile.load()
    profile.name = "Colectivo Norte"
    profile.tagline = "Poesía desde el desierto."
    profile.save()
    resp = client.get(reverse("content:home"))
    assert b"<title>Colectivo Norte" in resp.content
    assert b"Poes\xc3\xada desde el desierto." in resp.content
    assert b'property="og:site_name" content="Colectivo Norte"' in resp.content


def test_subscribe_creates_pending_subscriber(client):
    resp = client.post(reverse("community:subscribe"), {"email": "prensa@example.com", "apodo": ""})
    assert resp.status_code == 302
    sub = NewsletterSubscriber.objects.get(email="prensa@example.com")
    assert sub.status == NewsletterSubscriber.Status.PENDING


def test_subscribe_honeypot_drops_bots(client):
    client.post(reverse("community:subscribe"), {"email": "bot@spam.com", "apodo": "bot"})
    assert not NewsletterSubscriber.objects.filter(email="bot@spam.com").exists()


def test_subscribe_duplicate_email_is_idempotent(client):
    NewsletterSubscriber.objects.create(email="ya@example.com")
    resp = client.post(reverse("community:subscribe"), {"email": "ya@example.com", "apodo": ""})
    assert resp.status_code == 302
    assert NewsletterSubscriber.objects.filter(email="ya@example.com").count() == 1


def test_submissions_route_stays_alive(client):
    assert client.get(reverse("submissions:submit")).status_code == 200
