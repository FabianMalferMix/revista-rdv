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


def test_legal_pages_published():
    from django.test import Client

    c = Client()
    for slug in ["privacidad", "cookies", "terminos"]:
        assert c.get(reverse("content:page_detail", args=[slug])).status_code == 200


def test_footer_has_legal_links_and_consent(client):
    content = client.get(reverse("content:home")).content
    assert reverse("content:page_detail", args=["privacidad"]).encode() in content
    assert reverse("content:page_detail", args=["cookies"]).encode() in content
    assert b"pol\xc3\xadtica de privacidad" in content  # nota de consentimiento del form


def test_privacy_page_cites_ley_21719(client):
    # La política actualizada cita la Ley 21.719 (además de la 19.628).
    resp = client.get(reverse("content:page_detail", args=["privacidad"]))
    assert resp.status_code == 200
    assert b"21.719" in resp.content
    assert b"19.628" in resp.content
