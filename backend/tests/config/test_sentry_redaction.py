"""Lo que llega a Sentry no lleva datos de una persona ni los tokens del boletín.

Aun sin pedir datos personales, el SDK adjunta por defecto el cuerpo de las peticiones, las
variables locales de cada marco y las cabeceras, y el texto de un error SMTP cita la
dirección a la que no se pudo escribir. Estas pruebas arrancan Sentry como en producción
(`init_sentry`), con un transporte que guarda los eventos en vez de enviarlos, provocan
errores reales en el alta y en el envío del correo, y buscan en lo que se habría enviado.
Otras dos pasan un evento hecho a mano por `sentry_before_send`: el token de una ruta del
boletín sale tapado en la transacción y en la URL, y un evento con una forma inesperada se envía.
"""

import json
import secrets

import pytest
import sentry_sdk
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerError

from apps.community import views
from apps.community.models import NewsletterSubscriber
from apps.community.tasks import send_confirmation_email
from config import redaction
from config.redaction import sentry_before_send

pytestmark = pytest.mark.django_db
EMAIL = "ana.prueba@example.com"
NAME = "Ana Prueba"


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


# Las respuestas de un servidor SMTP que rechaza al destinatario, para siempre o por un rato (una
# lista gris), citan su dirección; y las sesiones que abre la tarea hasta rendirse.
@pytest.mark.parametrize(
    ("reply", "sessions"),
    [
        (f"550 5.1.1 <{EMAIL}>: Recipient address rejected: User unknown", 1),
        (f"450 4.2.0 <{EMAIL}>: Recipient address rejected: Greylisted", 1 + 8),
    ],
    ids=["definitivo", "temporal"],
)
def test_a_failed_confirmation_email_reaches_sentry_without_personal_data(
    sentry_events, smtp_server, task_failures_stay_in_the_task, reply, sessions
):
    """El servidor de correo rechaza al destinatario, y smtplib copia su respuesta, que cita
    la dirección, en el error que llega a Sentry: al primer intento si el rechazo es definitivo,
    y tras el último reintento si es temporal y no se levanta."""
    smtp_server.script["RCPT"] = reply  # en todas las sesiones
    sub = _pending()
    send_confirmation_email.apply(args=[sub.pk])
    assert smtp_server.sessions == sessions  # control: el caso tomó su camino

    events = sentry_events()
    assert events, "el fallo del envío tiene que llegar a Sentry"
    sent = json.dumps(events)
    # Control: lo que llegó es el rechazo, con la dirección tapada.
    assert "SMTPRecipientsRefused" in sent and "<correo>" in sent
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
        "type": "poesia",
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


def test_sentry_no_recibe_el_token():
    """Es el punto más serio: sin esto, el token viajaría a un TERCERO."""
    evento = {
        "transaction": "/novedades/baja/SECRETO-123/",
        "request": {"url": "https://sitio.cl/novedades/baja/SECRETO-123/"},
    }
    limpio = sentry_before_send(evento, {})
    # Control: el evento conserva la ruta, con el token tapado.
    assert limpio["transaction"] == "/novedades/baja/<redactado>/"
    assert limpio["request"]["url"] == "https://sitio.cl/novedades/baja/<redactado>/"
    assert "SECRETO-123" not in limpio["transaction"]
    assert "SECRETO-123" not in limpio["request"]["url"]


def test_la_redaccion_nunca_rompe_el_reporte():
    """Un evento con una forma inesperada se envía igual: la limpieza solo descarta lo que
    no pudo limpiar (`test_an_event_that_cannot_be_cleaned_is_not_sent`)."""
    assert sentry_before_send({"transaction": None, "request": "no-es-dict"}, {}) is not None
    assert sentry_before_send({}, {}) == {}


@pytest.mark.parametrize("name", ["community:confirm", "community:unsubscribe"])
def test_token_pages_send_no_referrer(client, name):
    sub = _pending()
    token = sub.confirm_token if name == "community:confirm" else sub.token
    assert client.get(reverse(name, args=[token]))["Referrer-Policy"] == "no-referrer"
    # Control positivo: el resto del sitio mantiene su política.
    assert client.get(reverse("site:home"))["Referrer-Policy"] == "same-origin"
