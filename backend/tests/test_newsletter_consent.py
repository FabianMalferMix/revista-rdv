"""Integridad del consentimiento del doble opt-in (hallazgos S-15, S-16, S-17)."""

from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.community.models import CONFIRM_TOKEN_TTL, NewsletterSubscriber

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def _pendiente(**extra):
    datos = {
        "email": "alguien@example.com",
        "token": "tok-baja",
        "confirm_token": "tok-confirm",
        "confirm_token_at": timezone.now(),
        "status": S.PENDING,
    }
    datos.update(extra)
    return NewsletterSubscriber.objects.create(**datos)


# ── S-16: los escáneres de correo no pueden confirmar ─────


def test_un_get_no_confirma_la_suscripcion():
    """Los escáneres de enlaces y las pasarelas antivirus visitan por GET todo lo que
    llega en un mensaje: si el GET confirmaba, el doble opt-in no probaba nada."""
    from django.test import Client

    sub = _pendiente()
    resp = Client().get(reverse("community:confirm", args=[sub.confirm_token]))
    assert resp.status_code == 200  # muestra el botón…
    sub.refresh_from_db()
    assert sub.status == S.PENDING  # …pero no confirma


def test_un_get_no_da_de_baja():
    from django.test import Client

    sub = _pendiente(status=S.CONFIRMED)
    Client().get(reverse("community:unsubscribe", args=[sub.token]))
    sub.refresh_from_db()
    assert sub.status == S.CONFIRMED


def test_el_post_del_formulario_si_confirma(client):
    sub = _pendiente()
    resp = client.post(reverse("community:confirm", args=[sub.confirm_token]))
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.status == S.CONFIRMED


def test_baja_en_un_clic_rfc8058(client):
    """El cliente de correo envía POST con `List-Unsubscribe=One-Click`, sin sesión ni
    token CSRF: la vista está exenta a propósito para que la baja funcione."""
    sub = _pendiente(status=S.CONFIRMED)
    resp = client.post(
        reverse("community:unsubscribe", args=[sub.token]),
        data="List-Unsubscribe=One-Click",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.status == S.UNSUBSCRIBED


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_el_correo_anuncia_el_un_clic():
    from apps.community.tasks import send_confirmation_email

    send_confirmation_email("a@example.com", "https://x/confirmar", "https://x/baja")
    cabeceras = mail.outbox[0].extra_headers
    assert cabeceras["List-Unsubscribe"] == "<https://x/baja>"
    assert cabeceras["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


# ── S-15: caducidad y un solo uso ─────────────────────────


def test_el_enlace_de_confirmacion_caduca(client):
    sub = _pendiente(confirm_token_at=timezone.now() - CONFIRM_TOKEN_TTL - timedelta(minutes=1))
    resp = client.post(reverse("community:confirm", args=[sub.confirm_token]))
    assert resp.status_code == 404
    sub.refresh_from_db()
    assert sub.status == S.PENDING


def test_el_token_de_confirmacion_es_de_un_solo_uso(client):
    sub = _pendiente()
    token = sub.confirm_token
    assert client.post(reverse("community:confirm", args=[token])).status_code == 200
    # Reutilizar el enlace ya no vale: el token se consumió.
    assert client.post(reverse("community:confirm", args=[token])).status_code == 404


def test_el_enlace_de_baja_no_caduca_nunca(client):
    """Un enlace de baja que deja de funcionar es un problema legal, no una mejora."""
    sub = _pendiente(status=S.CONFIRMED, confirm_token_at=timezone.now() - timedelta(days=900))
    sub.created_at = timezone.now() - timedelta(days=900)
    sub.save()
    resp = client.post(reverse("community:unsubscribe", args=[sub.token]))
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.status == S.UNSUBSCRIBED


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_reintentar_el_alta_emite_un_token_de_confirmacion_nuevo(client):
    sub = _pendiente()
    primero = sub.confirm_token
    client.post(reverse("community:subscribe"), {"email": sub.email, "apodo": ""})
    sub.refresh_from_db()
    assert sub.confirm_token != primero
    assert sub.token == "tok-baja", "el token de baja debe permanecer estable"


# ── S-17: sin oráculo de pertenencia ──────────────────────


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_el_alta_no_revela_si_la_direccion_ya_estaba_suscrita(client):
    """El mensaje distinguía «Ya estabas suscrito/a» de «Te enviamos un correo», así que
    cualquiera podía comprobar si una dirección concreta estaba en la lista."""
    NewsletterSubscriber.objects.create(email="conocida@example.com", status=S.CONFIRMED, token="t")

    def _mensaje(email):
        resp = client.post(
            reverse("community:subscribe"), {"email": email, "apodo": ""}, follow=True
        )
        return resp.content

    ya_suscrita = _mensaje("conocida@example.com")
    nueva = _mensaje("desconocida@example.com")
    assert b"Ya estabas" not in ya_suscrita
    # El texto visible es idéntico en ambos casos.
    marca = "Si la dirección es válida".encode()
    assert marca in ya_suscrita and marca in nueva


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_el_honeypot_tambien_responde_igual(client):
    """Un bot no debe distinguirse por la respuesta."""
    resp = client.post(
        reverse("community:subscribe"),
        {"email": "bot@example.com", "apodo": "soy-bot"},
        follow=True,
    )
    assert "Si la dirección es válida".encode() in resp.content
    assert not NewsletterSubscriber.objects.filter(email="bot@example.com").exists()
    assert len(mail.outbox) == 0
