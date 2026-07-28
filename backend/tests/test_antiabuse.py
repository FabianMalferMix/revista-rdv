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


# ── Resolución de IP tras el proxy (hallazgo #01: cubo global) ──────────────


def test_client_ip_uses_rightmost_forwarded_for_and_is_spoof_safe():
    """La IP se toma de la entrada MÁS A LA DERECHA de X-Forwarded-For (la que añade
    Caddy); un valor inyectado por el cliente a la izquierda se ignora."""
    from django.test import RequestFactory

    from config.clientip import client_ip

    req = RequestFactory().post(
        "/", HTTP_X_FORWARDED_FOR="1.2.3.4, 9.9.9.9, 203.0.113.7", REMOTE_ADDR="172.20.0.5"
    )
    assert client_ip(req) == "203.0.113.7"


def test_client_ip_falls_back_to_remote_addr_without_proxy():
    from django.test import RequestFactory

    from config.clientip import client_ip

    req = RequestFactory().post("/", REMOTE_ADDR="198.51.100.4")
    assert client_ip(req) == "198.51.100.4"


def test_axes_and_ratelimit_share_the_same_ip_resolver():
    """Regresión de #01: ambos controles deben resolver la IP con el MISMO callable;
    si divergen, el límite por IP se colapsa en un cubo global tras el proxy."""
    from django.conf import settings

    assert settings.RATELIMIT_IP_META_KEY == "config.clientip.client_ip"
    assert settings.AXES_CLIENT_IP_CALLABLE == "config.clientip.client_ip"


def test_rate_limit_buckets_are_isolated_per_client_ip(client):
    """Dos clientes reales distintos (distinta IP a la derecha de X-Forwarded-For) NO
    comparten el cupo: agotar el de uno no limita al otro (evita el DoS del cubo global)."""
    url = reverse("community:subscribe")
    ip_a = "203.0.113.10"
    for i in range(5):  # A agota su rate 5/m
        client.post(url, {"email": f"a{i}@example.com", "next": "/"}, HTTP_X_FORWARDED_FOR=ip_a)
    resp_a = client.post(
        url, {"email": "a-extra@example.com", "next": "/"}, HTTP_X_FORWARDED_FOR=ip_a, follow=True
    )
    assert b"Demasiados intentos" in resp_a.content  # A queda limitado
    # Cliente B, otra IP: su primer intento pasa (cupo independiente).
    resp_b = client.post(
        url,
        {"email": "b@example.com", "next": "/"},
        HTTP_X_FORWARDED_FOR="203.0.113.20",
        follow=True,
    )
    assert NewsletterSubscriber.objects.filter(email="b@example.com").exists()
    assert b"Demasiados intentos" not in resp_b.content
