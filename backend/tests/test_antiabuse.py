"""Anti-abuso: fuerza bruta (django-axes) y rate-limit por IP (django-ratelimit) — F2-5."""

import pytest
from bs4 import BeautifulSoup
from django.test import Client, override_settings
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


def test_subscribe_is_rate_limited_by_ip(client, frozen_rate_limit_window):
    url = reverse("community:subscribe")
    for i in range(5):  # rate 5/m: cinco pasan
        client.post(url, {"email": f"ok{i}@example.com", "next": "/"})
    # El sexto queda limitado: sin alta y con aviso.
    resp = client.post(url, {"email": "extra@example.com", "next": "/"}, follow=True)
    assert b"Demasiados intentos" in resp.content
    # Control: las cinco altas dentro del cupo sí quedaron.
    assert NewsletterSubscriber.objects.filter(email__startswith="ok").count() == 5
    assert not NewsletterSubscriber.objects.filter(email="extra@example.com").exists()


def test_the_rate_limit_notice_waits_by_the_field_with_what_was_typed(
    client, frozen_rate_limit_window
):
    """El aviso del límite va en la página del boletín, junto al campo y con el correo escrito,
    para volver a intentarlo sin reescribirlo."""
    url = reverse("community:subscribe")
    for i in range(5):
        client.post(url, {"email": f"ok{i}@example.com", "next": "/"})
    resp = client.post(url, {"email": "extra@example.com", "next": "/"})
    sopa = BeautifulSoup(resp.content, "html.parser")
    correo = sopa.select_one("main #news-email")
    assert correo["value"] == "extra@example.com"
    aviso = sopa.select_one(f"#{correo['aria-describedby'].split()[0]}")
    assert "Demasiados intentos" in aviso.get_text()


def test_subscribe_under_limit_still_works(client):
    url = reverse("community:subscribe")
    client.post(url, {"email": "primera@example.com", "next": "/"})
    assert NewsletterSubscriber.objects.filter(email="primera@example.com").exists()


def test_submit_is_rate_limited_by_ip(client, frozen_rate_limit_window):
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


def test_rate_limit_buckets_are_isolated_per_client_ip(client, frozen_rate_limit_window):
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


# ── Bloqueo por cuenta e IP ────────────────────────────────────

ATTACKER = "203.0.113.50"
OTHER_IP = "198.51.100.60"


def _login(client, username, password, ip):
    return client.post(
        reverse("admin:login"),
        {"username": username, "password": password, "next": "/admin/"},
        HTTP_X_FORWARDED_FOR=ip,
    )


@pytest.fixture
def two_staff_accounts(db):
    from django.contrib.auth import get_user_model

    model = get_user_model()
    model.objects.create_user("duena", password="clave-correcta-de-la-duena", is_staff=True)
    model.objects.create_user("autora", password="clave-correcta-de-la-autora", is_staff=True)


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
def test_failed_attempts_lock_the_account_only_from_that_ip(client, two_staff_accounts):
    for _ in range(3):
        _login(client, "duena", "no-es-su-clave", ATTACKER)
    # Desde esa IP, la cuenta queda bloqueada, aunque llegue la contraseña correcta.
    assert _login(client, "duena", "clave-correcta-de-la-duena", ATTACKER).status_code == 429
    # La dueña entra desde su conexión, y otra cuenta entra desde la misma IP.
    assert _login(Client(), "duena", "clave-correcta-de-la-duena", OTHER_IP).status_code == 302
    assert _login(Client(), "autora", "clave-correcta-de-la-autora", ATTACKER).status_code == 302


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
def test_another_account_logging_in_does_not_reset_the_count(client, two_staff_accounts):
    """Con el bloqueo por IP, una cuenta propia que acertaba cada pocos intentos reiniciaba el
    contador, y se podían probar contraseñas contra otra cuenta sin fin."""
    _login(client, "duena", "no-es-su-clave", ATTACKER)
    _login(client, "duena", "tampoco", ATTACKER)
    assert _login(Client(), "autora", "clave-correcta-de-la-autora", ATTACKER).status_code == 302
    _login(client, "duena", "ni-esta", ATTACKER)
    assert _login(client, "duena", "clave-correcta-de-la-duena", ATTACKER).status_code == 429
