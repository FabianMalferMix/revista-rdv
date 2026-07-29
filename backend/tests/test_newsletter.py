"""Newsletter con doble opt-in + baja, y páginas legales (Lote F1-E)."""

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.community.models import NewsletterSubscriber

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_sends_confirmation_with_link(client):
    client.post(reverse("community:subscribe"), {"email": "nuevo@example.com", "apodo": ""})
    sub = NewsletterSubscriber.objects.get(email="nuevo@example.com")
    assert sub.status == S.PENDING and sub.token
    assert len(mail.outbox) == 1
    assert reverse("community:confirm", args=[sub.token]) in mail.outbox[0].body


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_confirmation_email_task_sends_message():
    # El envío vive en una tarea Celery (fuera del hilo de la petición, con reintento).
    from apps.community.tasks import send_confirmation_email

    send_confirmation_email("a@example.com", "https://x/confirmar", "https://x/baja")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["a@example.com"]
    assert "https://x/confirmar" in mail.outbox[0].body


def test_confirm_sets_confirmed(client):
    NewsletterSubscriber.objects.create(email="x@example.com", token="tok-confirm")
    resp = client.get(reverse("community:confirm", args=["tok-confirm"]))
    assert resp.status_code == 200
    sub = NewsletterSubscriber.objects.get(email="x@example.com")
    assert sub.status == S.CONFIRMED and sub.confirmed_at is not None


def test_unsubscribe_sets_unsubscribed(client):
    NewsletterSubscriber.objects.create(email="y@example.com", token="tok-baja", status=S.CONFIRMED)
    resp = client.get(reverse("community:unsubscribe", args=["tok-baja"]))
    assert resp.status_code == 200
    sub = NewsletterSubscriber.objects.get(email="y@example.com")
    assert sub.status == S.UNSUBSCRIBED


def test_confirm_bad_token_404(client):
    assert client.get(reverse("community:confirm", args=["no-existe"])).status_code == 404


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_already_confirmed_not_reconfirmed(client):
    NewsletterSubscriber.objects.create(email="z@example.com", status=S.CONFIRMED, token="t")
    client.post(reverse("community:subscribe"), {"email": "z@example.com", "apodo": ""})
    assert len(mail.outbox) == 0  # no reenvía a quien ya confirmó


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_honeypot_sends_no_mail(client):
    client.post(reverse("community:subscribe"), {"email": "bot@spam.com", "apodo": "bot"})
    assert not NewsletterSubscriber.objects.filter(email="bot@spam.com").exists()
    assert len(mail.outbox) == 0


def test_subscribe_long_email_rejected_cleanly_not_500(client):
    """Un correo con formato válido pero de >254 caracteres se rechaza con error de
    validación, no revienta en un HTTP 500 (DataError) al insertarse (hallazgo #03)."""
    long_email = "a" * 250 + "@example.com"  # 262 caracteres, formato válido
    resp = client.post(
        reverse("community:subscribe"), {"email": long_email, "apodo": ""}, follow=True
    )
    assert resp.status_code == 200  # no 500
    assert not NewsletterSubscriber.objects.filter(email=long_email).exists()
    assert b"Revisa el correo" in resp.content


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_next_open_redirect_is_blocked(client):
    """Un `next` hacia un host externo se ignora: la redirección se queda en el
    sitio (evita el open redirect CWE-601, hallazgo #07)."""
    resp = client.post(
        reverse("community:subscribe"),
        {"email": "safe@example.com", "apodo": "", "next": "https://evil.example/phish"},
    )
    assert resp.status_code == 302
    assert "evil.example" not in resp["Location"]
    assert resp["Location"] == reverse("content:home")


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_next_same_site_is_honored(client):
    """Un `next` a una ruta del propio sitio sí se respeta."""
    resp = client.post(
        reverse("community:subscribe"),
        {"email": "safe2@example.com", "apodo": "", "next": "/textos/"},
    )
    assert resp.status_code == 302
    assert resp["Location"] == "/textos/"


def test_subscribe_degrades_gracefully_when_broker_is_down(client):
    """Si el broker está caído al encolar el correo, el alta NO revienta con 500: el
    suscriptor queda guardado y el fallo se registra (hallazgo: degradación Celery)."""
    from unittest import mock

    from kombu.exceptions import OperationalError

    from apps.community import views

    def enqueue_fail(*a, **k):
        raise OperationalError("broker inaccesible")

    with mock.patch.object(views.send_confirmation_email, "delay", enqueue_fail):
        resp = client.post(
            reverse("community:subscribe"), {"email": "broker@example.com", "apodo": ""}
        )
    assert resp.status_code == 302  # redirección normal, no 500
    assert NewsletterSubscriber.objects.filter(email="broker@example.com").exists()


def test_email_task_declares_retry_policy():
    """La tarea de correo reintenta ante fallos transitorios de SMTP/red (política)."""
    import smtplib

    from apps.community.tasks import send_confirmation_email

    assert smtplib.SMTPException in send_confirmation_email.autoretry_for
    assert OSError in send_confirmation_email.autoretry_for
    assert send_confirmation_email.retry_kwargs["max_retries"] == 3


def test_email_task_does_not_swallow_smtp_errors(monkeypatch):
    """Sin fail_silently: un fallo definitivo de SMTP se propaga (sube a Sentry) en vez
    de tragarse en silencio."""
    import smtplib

    from apps.community import tasks

    def boom(*a, **k):
        raise smtplib.SMTPException("smtp caído")

    monkeypatch.setattr(tasks, "send_mail", boom)
    with pytest.raises(smtplib.SMTPException):
        tasks.send_confirmation_email("a@example.com", "http://c", "http://u")


def test_legal_pages_published(legal_pages):
    from django.test import Client

    c = Client()
    for slug in ["privacidad", "cookies", "terminos"]:
        assert c.get(reverse("content:page_detail", args=[slug])).status_code == 200


def test_footer_has_legal_links_and_consent(client):
    content = client.get(reverse("content:home")).content
    assert reverse("content:page_detail", args=["privacidad"]).encode() in content
    assert reverse("content:page_detail", args=["cookies"]).encode() in content
    assert b"pol\xc3\xadtica de privacidad" in content  # nota de consentimiento del form


def test_privacy_page_cites_ley_21719(client, legal_pages):
    # La política actualizada cita la Ley 21.719 (además de la 19.628).
    resp = client.get(reverse("content:page_detail", args=["privacidad"]))
    assert resp.status_code == 200
    assert b"21.719" in resp.content
    assert b"19.628" in resp.content
