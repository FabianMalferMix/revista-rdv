"""Lo que llega a Sentry no lleva datos de una persona ni los tokens del boletín.

Aun sin pedir datos personales, el SDK adjunta por defecto el cuerpo de las peticiones, las
variables locales de cada marco y las cabeceras, y el texto de un error SMTP cita la
dirección a la que no se pudo escribir. Estas pruebas arrancan Sentry como en producción
(`init_sentry`), con un transporte que guarda los eventos en vez de enviarlos, provocan
errores reales en el alta y en el envío del correo, y buscan en lo que se habría enviado.
"""

import json
import secrets
import smtplib

import pytest
import sentry_sdk
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerError
from sentry_sdk.transport import Transport

from apps.community import views
from apps.community.models import NewsletterSubscriber
from apps.community.tasks import send_confirmation_email
from config import redaction
from config.sentry import init_sentry

pytestmark = pytest.mark.django_db
EMAIL = "ana.prueba@example.com"
NAME = "Ana Prueba"
# La respuesta de un servidor SMTP que rechaza al destinatario: cita su dirección.
SMTP_REPLY = f"5.1.1 <{EMAIL}>: Recipient address rejected: User unknown".encode()


class _KeepEvents(Transport):
    """Un transporte que guarda los sobres en vez de mandarlos."""

    def __init__(self):
        super().__init__()
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

    def events(self):
        return [e for env in self.envelopes if (e := env.get_event()) is not None]


@pytest.fixture
def sentry_events():
    transport = _KeepEvents()
    init_sentry("https://public@sentry.invalid/1", environment="test", transport=transport)
    yield transport.events
    sentry_sdk.get_client().close()


def _pending():
    # Tokens al azar, como los reales: Sentry adjunta las líneas de código vecinas de cada
    # marco, y un token escrito aquí aparecería en ellas.
    return NewsletterSubscriber.objects.create(
        email=EMAIL,
        token=secrets.token_urlsafe(),
        confirm_token=secrets.token_urlsafe(),
        confirm_token_at=timezone.now(),
    )


def _secrets(sub):
    return [EMAIL, sub.token, sub.confirm_token]


def test_an_error_while_subscribing_reaches_sentry_without_personal_data(
    sentry_events, client, monkeypatch
):
    def broker_down(*args, **kwargs):
        raise BrokerError("broker inaccesible")

    monkeypatch.setattr(views.send_confirmation_email, "delay_on_commit", broker_down)
    other_token = secrets.token_urlsafe()
    page = f"https://revista.example.org{reverse('community:unsubscribe', args=[other_token])}"
    client.post(
        reverse("community:subscribe"),
        {"email": EMAIL, "apodo": "", "next": "/"},
        HTTP_REFERER=page,
        HTTP_HX_CURRENT_URL=page,
    )
    sub = NewsletterSubscriber.objects.get(email=EMAIL)

    events = sentry_events()
    assert events, "el error del alta tiene que llegar a Sentry"
    sent = json.dumps(events)
    for secret in [*_secrets(sub), other_token]:
        assert secret not in sent


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_a_failed_confirmation_email_reaches_sentry_without_personal_data(
    sentry_events, monkeypatch
):
    sub = _pending()

    def refused(self, *args, **kwargs):
        raise smtplib.SMTPRecipientsRefused({EMAIL: (550, SMTP_REPLY)})

    monkeypatch.setattr("django.core.mail.EmailMessage.send", refused)
    send_confirmation_email.apply(args=[sub.pk])

    events = sentry_events()
    assert events, "el fallo del envío tiene que llegar a Sentry"
    sent = json.dumps(events)
    for secret in _secrets(sub):
        assert secret not in sent


def test_an_error_while_submitting_a_text_reaches_sentry_without_personal_data(
    sentry_events, monkeypatch, client
):
    """Un 500 en el formulario de propuestas: el cuerpo de la petición lleva el nombre, el
    correo, el título y el texto de quien envía."""

    def save_fails(self, *args, **kwargs):
        raise RuntimeError("no se pudo guardar el envío")

    monkeypatch.setattr("apps.submissions.models.Submission.save", save_fails)
    client.raise_request_exception = False
    text = {
        "author_name": NAME,
        "author_email": EMAIL,
        "type": "poesía",
        "title": "Título del inédito",
        "body": "Versos del inédito que nadie más ha leído",
    }
    assert client.post(reverse("submissions:submit"), text).status_code == 500

    events = sentry_events()
    assert events, "el 500 tiene que llegar a Sentry"
    sent = json.dumps(events, ensure_ascii=False)
    for secret in (NAME, EMAIL, "Título del inédito", "Versos del inédito"):
        assert secret not in sent


def test_an_event_that_cannot_be_cleaned_is_not_sent(sentry_events, monkeypatch):
    def broken(value):
        raise RuntimeError("redacción rota")

    monkeypatch.setattr(redaction, "_scrub", broken)
    sentry_sdk.capture_message(f"Alta de {EMAIL}")
    assert sentry_events() == []


def test_a_clean_event_is_sent(sentry_events):
    """Control positivo de la anterior: con la redacción en pie, el mensaje sale, sin el
    correo."""
    sentry_sdk.capture_message(f"Alta de {EMAIL}")
    (event,) = sentry_events()
    assert event["message"] == "Alta de <correo>"


@pytest.mark.parametrize("name", ["community:confirm", "community:unsubscribe"])
def test_token_pages_send_no_referrer(client, name):
    sub = _pending()
    token = sub.confirm_token if name == "community:confirm" else sub.token
    assert client.get(reverse(name, args=[token]))["Referrer-Policy"] == "no-referrer"
    # Control positivo: el resto del sitio mantiene su política.
    assert client.get(reverse("content:home"))["Referrer-Policy"] == "same-origin"
