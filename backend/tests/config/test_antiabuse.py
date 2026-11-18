"""El abuso de lo público: el límite de peticiones por IP de la búsqueda, el alta al boletín y
el envío de propuestas (config/ratelimit.py), y el bloqueo del acceso al panel tras los intentos
fallidos (django-axes).

Pasado el límite, el alta no se guarda y responde la página de siempre, con su aviso (en la del
boletín, junto al campo y con el correo escrito), y un 429 que dice en Retry-After cuánto falta
para que se renueve la ventana. La IP de cada cliente es la última de X-Forwarded-For, la que
añade el proxy, o la de la conexión si no hay proxy; los dos controles la resuelven igual, y
cada cliente tiene su propio cupo. Los intentos fallidos bloquean la cuenta solo desde esa IP,
aunque llegue la contraseña correcta, y el acierto de otra cuenta desde esa IP no pone el
contador a cero.
"""

import time

import pytest
from bs4 import BeautifulSoup
from django.test import Client, override_settings
from django.urls import reverse

from apps.community.models import NewsletterSubscriber

pytestmark = pytest.mark.django_db


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


# ── Pasado el límite: la página de siempre, con un 429 ─────────────────────


def _search(client):
    return client.get(reverse("site:search"), {"q": "umbral"})


def _subscribe(client):
    return client.post(reverse("community:subscribe"), {"email": "ana@example.org", "next": "/"})


def _submit(client):
    return client.post(reverse("submissions:submit"), {"title": "Un título"})


# Cada vista con límite: la petición, cuántas pasan en una ventana y con qué respuesta, el
# título de su página y dónde va el aviso, con su comienzo.
LIMITED = {
    "search": (_search, 60, 200, "Búsqueda", "main .empty", "Demasiadas búsquedas"),
    "subscribe": (
        _subscribe,
        5,
        302,
        "Suscripción a las novedades",
        "main .news-error",
        "Demasiados intentos",
    ),
    "submit": (_submit, 10, 200, "Enviar una propuesta", ".flash-error", "Has enviado demasiadas"),
}


@pytest.mark.parametrize("view", sorted(LIMITED))
def test_past_the_limit_the_usual_page_answers_429(client, frozen_rate_limit_window, view):
    """Pasado el límite responde la página de siempre, con su aviso, y un 429 que dice en
    Retry-After cuántos segundos faltan para que la ventana del contador se renueve. Control:
    la última petición dentro del cupo pasa como siempre."""
    send, allowed, status, title, where, notice = LIMITED[view]
    for _ in range(allowed):
        response = send(client)
    assert response.status_code == status
    response = send(client)
    left = frozen_rate_limit_window - int(time.time())
    assert response.status_code == 429
    assert left <= int(response["Retry-After"]) <= left + 1
    page = BeautifulSoup(response.content, "html.parser")
    assert page.select_one("main h1").get_text(strip=True) == title
    assert page.select_one(where).get_text(strip=True).startswith(notice)


# ── Resolución de IP tras el proxy: un cupo por cliente, no uno global ──────


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
    """Ambos controles resuelven la IP con el MISMO callable: si divergieran, el límite por
    IP se colapsaría en un cubo global tras el proxy."""
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
    """Un acierto reinicia solo el contador de su cuenta desde su IP: si reiniciara el de la
    IP, una cuenta propia que acertara cada pocos intentos lo pondría a cero, y se podrían
    probar contraseñas contra otra cuenta sin fin."""
    _login(client, "duena", "no-es-su-clave", ATTACKER)
    _login(client, "duena", "tampoco", ATTACKER)
    assert _login(Client(), "autora", "clave-correcta-de-la-autora", ATTACKER).status_code == 302
    _login(client, "duena", "ni-esta", ATTACKER)
    assert _login(client, "duena", "clave-correcta-de-la-duena", ATTACKER).status_code == 429
