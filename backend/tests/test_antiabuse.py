"""Anti-abuso: fuerza bruta (django-axes) y rate-limit por IP (django-ratelimit) — F2-5."""

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.community.models import NewsletterSubscriber

pytestmark = pytest.mark.django_db


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
def test_axes_locks_out_repeated_failed_admin_logins(client):
    from axes.utils import reset

    reset()
    url = reverse("admin:login")
    for _ in range(3):
        client.post(url, {"username": "atacante", "password": "malo"})
    # Superado el límite, axes bloquea la IP con 429 (Too Many Requests), no el login (200).
    resp = client.post(url, {"username": "atacante", "password": "malo"})
    assert resp.status_code in (403, 429)
    reset()


def test_subscribe_is_rate_limited_by_ip(client):
    url = reverse("community:subscribe")
    for i in range(5):  # rate 5/m: cinco pasan
        client.post(url, {"email": f"ok{i}@example.com", "next": "/"})
    # El sexto queda limitado: sin alta y con aviso.
    resp = client.post(url, {"email": "extra@example.com", "next": "/"}, follow=True)
    assert not NewsletterSubscriber.objects.filter(email="extra@example.com").exists()
    assert b"Demasiados intentos" in resp.content


def test_subscribe_under_limit_still_works(client):
    url = reverse("community:subscribe")
    client.post(url, {"email": "primera@example.com", "next": "/"})
    assert NewsletterSubscriber.objects.filter(email="primera@example.com").exists()


def test_submit_is_rate_limited_by_ip(client):
    url = reverse("submissions:submit")
    for _ in range(10):  # rate 10/h
        client.post(url, {})
    resp = client.post(url, {})
    assert b"demasiadas propuestas" in resp.content
