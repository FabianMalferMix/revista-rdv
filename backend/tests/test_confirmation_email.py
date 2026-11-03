"""El correo de confirmación llega aunque el proveedor falle un rato, y deja rastro.

Lo transitorio (una caída, un 4xx) se reintenta durante hasta una hora, con esperas que
crecen; un rechazo permanente no se reintenta. El panel muestra cuándo salió el correo o por qué no, y
deja reenviarlo a quien sigue pendiente.
"""

import smtplib

import pytest
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


@pytest.fixture
def flaky():
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


def test_a_permanent_rejection_is_not_retried_and_shows_in_the_panel(flaky, client, editor):
    sub = _pending()
    flaky.append(smtplib.SMTPRecipientsRefused({EMAIL: (550, b"5.1.1 user unknown")}))
    send_confirmation_email.apply(args=[sub.pk])
    assert FlakyBackend.calls == 1
    sub.refresh_from_db()
    assert sub.confirmation_sent_at is None
    assert sub.confirmation_error == "SMTPRecipientsRefused 550"
    client.force_login(editor)
    page = client.get(f"/admin/community/newslettersubscriber/{sub.pk}/change/").content.decode()
    assert "SMTPRecipientsRefused 550" in page


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
    assert requested["max_retries"] == 8


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_the_email_names_the_collective_and_links_from_the_site_url(settings):
    settings.SITE_URL = "https://revista.example.org"
    profile = SiteProfile.load()
    profile.name = "Colectivo de Prueba"
    profile.save()
    sub = _pending()
    send_confirmation_email(sub.pk)
    (message,) = mail.outbox
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
