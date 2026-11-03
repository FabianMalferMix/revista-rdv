"""Una dirección que el servidor de correo rechaza no queda en el log del worker.

Al rechazar el destinatario, smtplib lanza SMTPRecipientsRefused con la dirección dentro, y
Celery copia la excepción en la línea de error de la tarea: en el mensaje, en la traza y en el
extra `data`. El log de producción (JSON) la sustituye por una marca, como Sentry, y deja el
resto de la línea, que es lo que sirve para diagnosticar.
"""

import io
import json
import logging
import socketserver
import threading
from copy import deepcopy

import pytest
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.community.tasks import send_confirmation_email
from config.celery import app as celery_app
from config.logformat import JsonFormatter

pytestmark = pytest.mark.django_db
EMAIL = "lectora.rechazada@example.com"


class _RejectingSMTP(socketserver.StreamRequestHandler):
    """Un servidor SMTP mínimo: acepta la conexión y el remitente, y rechaza al destinatario."""

    def handle(self):
        self.reply("220 localhost ESMTP")
        for raw in self.rfile:
            verb, _, argument = raw.decode().strip().partition(" ")
            if verb.upper() == "RCPT":
                self.server.refused.append(argument[argument.index("<") + 1 : argument.index(">")])
                self.reply("550 5.1.1 Recipient address rejected: user unknown")
            elif verb.upper() == "QUIT":
                self.reply("221 Bye")
                return
            else:
                self.reply("250 OK")

    def reply(self, line):
        self.wfile.write(f"{line}\r\n".encode())


@pytest.fixture
def rejecting_smtp(settings):
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _RejectingSMTP)
    server.daemon_threads = True
    server.refused = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST, settings.EMAIL_PORT = server.server_address
    settings.EMAIL_HOST_USER = settings.EMAIL_HOST_PASSWORD = ""
    settings.EMAIL_USE_TLS = settings.EMAIL_USE_SSL = False
    yield server
    server.shutdown()
    server.server_close()


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


def test_a_refused_recipient_is_not_in_the_worker_log(rejecting_smtp, worker_log):
    sub = NewsletterSubscriber.objects.create(
        email=EMAIL, token="baja-tok", confirm_token="alta-tok", confirm_token_at=timezone.now()
    )
    send_confirmation_email.apply(args=[sub.pk])

    assert rejecting_smtp.refused == [EMAIL]
    lines = worker_log()
    failure = next(
        line for line in lines if line["logger"] == "celery.app.trace" and line["level"] == "ERROR"
    )
    assert "SMTPRecipientsRefused" in failure["message"]
    assert "<correo>" in failure["message"] and "550" in failure["message"]
    assert "SMTPRecipientsRefused" in failure["exc_info"]
    assert EMAIL not in json.dumps(lines)
