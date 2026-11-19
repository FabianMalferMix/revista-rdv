"""El correo de confirmación llega aunque el proveedor falle un rato, y deja rastro.

Lo que el servidor de correo rechaza por un rato (un 4xx, como una lista gris), una caída o un
servidor que no contesta se reintentan durante unos sesenta minutos como mucho, con esperas que
crecen. Lo que rechaza para siempre (un 5xx) no se reintenta, sea en el paso que sea, ni lo que
el servidor no ofrece, y cada sesión se cierra, también si el servidor rechaza a mitad. El panel
muestra cuándo salió el correo o por qué no, y deja reenviarlo a quien sigue pendiente.
"""

import smtplib

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.community.tasks import send_confirmation_email
from apps.showcase.models import SiteProfile
from tests import mail_backends
from tests.mail_backends import FlakyBackend

pytestmark = pytest.mark.django_db
EMAIL = "lectora@example.com"
# Cada paso de la sesión SMTP en que el servidor puede rechazar el correo: la excepción con la
# que smtplib lo cuenta, una respuesta temporal y una definitiva.
STEPS = {
    "greeting": (
        "SMTPConnectError",
        "421 4.3.2 Service not available",
        "554 5.3.2 No SMTP service here",
    ),
    "EHLO": ("SMTPHeloError", "421 4.3.0 Try again later", "550 5.7.1 Access denied"),
    "AUTH": (
        "SMTPAuthenticationError",
        "454 4.7.0 Temporary authentication failure",
        "535 5.7.8 Authentication credentials invalid",
    ),
    "MAIL": (
        "SMTPSenderRefused",
        "451 4.4.3 Sender domain not found, try again later",
        "553 5.7.1 Sender address rejected",
    ),
    "RCPT": (
        "SMTPRecipientsRefused",
        "450 4.2.0 Greylisted, try again later",
        "550 5.1.1 User unknown",
    ),
    "DATA": (
        "SMTPDataError",
        "451 4.3.0 Temporary local problem",
        "554 5.7.1 Message rejected as spam",
    ),
}


@pytest.fixture
def flaky(task_failures_stay_in_the_task):
    FlakyBackend.calls = 0
    mail_backends.failures.clear()
    with override_settings(EMAIL_BACKEND="tests.mail_backends.FlakyBackend"):
        yield mail_backends.failures


def _pending():
    return NewsletterSubscriber.objects.create(
        email=EMAIL, token="baja-tok", confirm_token="alta-tok", confirm_token_at=timezone.now()
    )


def test_a_server_that_fails_twice_then_accepts_delivers_and_records_it(flaky):
    sub = _pending()
    flaky.extend([smtplib.SMTPServerDisconnected("se cortó"), OSError("sin red")])
    send_confirmation_email.apply(args=[sub.pk])
    assert FlakyBackend.calls == 3
    assert [m.to for m in mail.outbox] == [[EMAIL]]
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is not None and sub.confirmation_error == ""


def test_a_send_that_outlasts_the_soft_time_limit_is_retried(flaky):
    """El límite blando de Celery corta un envío que no termina a tiempo, y el siguiente
    intento sale."""
    sub = _pending()
    flaky.append(SoftTimeLimitExceeded())
    send_confirmation_email.apply(args=[sub.pk])
    assert FlakyBackend.calls == 2
    assert [m.to for m in mail.outbox] == [[EMAIL]]
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is not None and sub.confirmation_error == ""


@pytest.mark.parametrize("step", STEPS)
def test_a_temporary_rejection_is_retried_and_the_email_goes_out(
    smtp_server, task_failures_stay_in_the_task, step
):
    _, temporary, _ = STEPS[step]
    smtp_server.script[step] = [temporary]  # solo en la primera sesión
    sub = _pending()
    send_confirmation_email.apply(args=[sub.pk])
    assert (smtp_server.sessions, smtp_server.unfinished) == (2, 0)
    (message,) = smtp_server.messages
    assert f"To: {EMAIL}" in message.splitlines()
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is not None and sub.confirmation_error == ""


@pytest.mark.parametrize("step", STEPS)
def test_a_definitive_rejection_is_not_retried_and_shows_in_the_panel(
    smtp_server, task_failures_stay_in_the_task, client, editor, step
):
    error, _, definitive = STEPS[step]
    smtp_server.script[step] = definitive  # en todas las sesiones
    sub = _pending()
    send_confirmation_email.apply(args=[sub.pk])
    assert (smtp_server.sessions, smtp_server.unfinished) == (1, 0)  # y la cerró
    assert smtp_server.messages == []
    shown = f"{error} {definitive[:3]}"
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is None and sub.confirmation_error == shown
    client.force_login(editor)
    page = client.get(f"/admin/community/newslettersubscriber/{sub.pk}/change/").content.decode()
    assert shown in page


def test_a_temporary_rejection_that_never_lifts_ends_in_the_panel(
    smtp_server, task_failures_stay_in_the_task
):
    smtp_server.script["RCPT"] = "450 4.2.0 Greylisted, try again later"  # en todas las sesiones
    sub = _pending()
    result = send_confirmation_email.apply(args=[sub.pk])
    assert smtp_server.sessions == 1 + 8  # el primer intento y los ocho reintentos
    assert isinstance(result.result, smtplib.SMTPRecipientsRefused)
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is None
    assert sub.confirmation_error == "SMTPRecipientsRefused 450"


def test_an_extension_the_server_lacks_is_not_retried(
    smtp_server, task_failures_stay_in_the_task, settings
):
    """Se pide STARTTLS a un servidor que no lo ofrece: insistir no lo cambia."""
    settings.EMAIL_USE_TLS = True
    sub = _pending()
    send_confirmation_email.apply(args=[sub.pk])
    assert (smtp_server.sessions, smtp_server.unfinished) == (1, 0)
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is None
    assert sub.confirmation_error == "SMTPNotSupportedError"


def test_a_login_method_the_server_lacks_is_not_retried(
    smtp_server, task_failures_stay_in_the_task
):
    """El servidor solo ofrece un modo de iniciar sesión que smtplib no sabe usar."""
    smtp_server.script["EHLO"] = "250-localhost\r\n250 AUTH XOAUTH2"
    sub = _pending()
    send_confirmation_email.apply(args=[sub.pk])
    assert (smtp_server.sessions, smtp_server.unfinished) == (1, 0)
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is None
    assert sub.confirmation_error == "SMTPException"


def test_email_task_does_not_swallow_smtp_errors(smtp_server):
    """Sin fail_silently: con él, el backend de Django se tragaría el rechazo, el panel diría
    que el correo salió y Sentry no se enteraría."""
    smtp_server.script["DATA"] = "554 5.7.1 Message rejected as spam"
    sub = _pending()
    with pytest.raises(smtplib.SMTPDataError):
        send_confirmation_email(sub.pk)
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is None
    assert sub.confirmation_error == "SMTPDataError 554"


@pytest.mark.parametrize(("retries", "wait"), [(0, 30), (3, 240), (7, 900)])
def test_a_transient_error_asks_celery_to_retry_later(flaky, monkeypatch, retries, wait):
    """En modo eager el reintento corre en el acto: aquí se mira lo que se le pide a Celery.
    Cada espera se sortea por debajo de su tope (jitter); la prueba la fija en el tope."""
    requested = {}

    class RetryRequested(Exception):
        pass

    def retry(**kwargs):
        requested.update(kwargs)
        raise RetryRequested

    monkeypatch.setattr(send_confirmation_email, "retry", retry)
    monkeypatch.setattr("random.randrange", lambda stop: stop - 1)
    flaky.append(smtplib.SMTPConnectError(421, b"vuelve luego"))
    send_confirmation_email.apply(args=[_pending().pk], retries=retries)
    assert isinstance(requested["exc"], smtplib.SMTPConnectError)
    assert requested["countdown"] == wait


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_the_email_names_the_collective_and_links_from_the_site_url(settings):
    settings.SITE_URL = "https://revista.example.org"
    profile = SiteProfile.load()
    profile.name = "Colectivo de Prueba"
    profile.save()
    sub = _pending()
    send_confirmation_email(sub.pk)
    (message,) = mail.outbox
    assert message.to == [EMAIL]
    assert message.subject == "Confirma tu suscripción a las novedades de Colectivo de Prueba"
    assert "Gracias por suscribirte a las novedades de Colectivo de Prueba." in message.body
    assert (
        f"https://revista.example.org{reverse('community:confirm', args=['alta-tok'])}"
        in message.body
    )
    assert message.extra_headers["List-Unsubscribe"] == (
        f"<https://revista.example.org{reverse('community:unsubscribe', args=['baja-tok'])}>"
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_resending_from_the_panel_reaches_only_pending_subscribers(
    client, editor, django_capture_on_commit_callbacks
):
    pending = _pending()
    confirmed = NewsletterSubscriber.objects.create(email="ya@example.com", status="confirmed")
    client.force_login(editor)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            "/admin/community/newslettersubscriber/",
            {"action": "do_resend", "_selected_action": [pending.pk, confirmed.pk]},
        )
    assert [m.to for m in mail.outbox] == [[EMAIL]]
    pending.refresh_from_db()
    assert pending.confirm_token != "alta-tok"  # un enlace nuevo


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_without_the_change_permission_the_panel_neither_resends_nor_unsubscribes(
    client, editor, django_capture_on_commit_callbacks
):
    """Si el operador deja a un rol solo con la vista de los suscriptores, las acciones que
    cambian su estado desaparecen, y un POST directo no hace nada."""
    sub = _pending()
    group = editor.groups.get()
    group.permissions.remove(Permission.objects.get(codename="change_newslettersubscriber"))
    client.force_login(editor)
    changelist = "/admin/community/newslettersubscriber/"
    page = client.get(changelist).content.decode()
    assert EMAIL in page  # control positivo: la vista sigue
    assert "do_resend" not in page and "do_unsubscribe" not in page
    for action in ("do_resend", "do_unsubscribe"):
        with django_capture_on_commit_callbacks(execute=True):
            client.post(changelist, {"action": action, "_selected_action": [sub.pk]})
    sub.refresh_from_db()
    assert (sub.status, sub.confirm_token) == ("pending", "alta-tok")
    assert mail.outbox == []
