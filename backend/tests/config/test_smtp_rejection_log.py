"""Una dirección que el servidor de correo rechaza no queda en el log del worker.

Al rechazar el destinatario, smtplib lanza SMTPRecipientsRefused con la dirección dentro, y
Celery copia la excepción en lo que escribe de la tarea: en la línea del reintento, si el rechazo
es temporal, y en la del error, si es definitivo (en el mensaje, en la traza y en el extra
`data`). El log de producción (JSON) la sustituye por una marca, como Sentry, y deja el resto de
la línea, que es lo que sirve para diagnosticar.
"""

import io
import json
import logging
from copy import deepcopy

import pytest
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.community.tasks import send_confirmation_email
from config.celery import app as celery_app
from config.logformat import JsonFormatter

pytestmark = pytest.mark.django_db
EMAIL = "lectora.rechazada@example.com"


@pytest.fixture
def worker_log(settings):
    """El log del worker como en producción: Celery lo configura con el LOGGING en JSON, y
    la consola escribe en un búfer en lugar de stderr."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    production = deepcopy(settings.LOGGING)
    production["handlers"]["console"]["formatter"] = "json"
    settings.LOGGING = production
    celery_app.log.already_setup = False
    celery_app.log.setup_logging_subsystem()
    stream = io.StringIO()
    (console,) = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
    console.setStream(stream)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    root.handlers[:] = handlers
    root.setLevel(level)


def _send():
    sub = NewsletterSubscriber.objects.create(
        email=EMAIL, token="baja-tok", confirm_token="alta-tok", confirm_token_at=timezone.now()
    )
    send_confirmation_email.apply(args=[sub.pk])


def test_a_refused_recipient_is_not_in_the_worker_log(
    smtp_server, worker_log, task_failures_stay_in_the_task
):
    smtp_server.script["RCPT"] = "550 5.1.1 Recipient address rejected: user unknown"
    _send()

    assert smtp_server.recipients == [EMAIL]
    lines = worker_log()
    failure = next(
        line for line in lines if line["logger"] == "celery.app.trace" and line["level"] == "ERROR"
    )
    assert "SMTPRecipientsRefused" in failure["message"]
    assert "<correo>" in failure["message"] and "550" in failure["message"]
    assert "SMTPRecipientsRefused" in failure["exc_info"]
    assert EMAIL not in json.dumps(lines)


def test_a_greylisted_recipient_is_not_in_the_retry_line(
    smtp_server, worker_log, task_failures_stay_in_the_task
):
    smtp_server.script["RCPT"] = ["450 4.2.0 Greylisted, try again later"]
    _send()

    assert smtp_server.recipients == [EMAIL, EMAIL]  # el rechazo y el reintento, que sale
    lines = worker_log()
    (retry,) = [
        line
        for line in lines
        if line["logger"] == "celery.app.trace" and " retry: " in line["message"]
    ]
    assert "SMTPRecipientsRefused" in retry["message"]
    assert "<correo>" in retry["message"] and "450" in retry["message"]
    assert EMAIL not in json.dumps(lines)
