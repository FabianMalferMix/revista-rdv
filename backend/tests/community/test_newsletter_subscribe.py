"""El alta en el boletín deja a la suscriptora pendiente, una sola vez por dirección."""

import pytest
from django.urls import reverse

from apps.community.models import NewsletterSubscriber

pytestmark = pytest.mark.django_db


def test_subscribe_creates_pending_subscriber(client):
    resp = client.post(reverse("community:subscribe"), {"email": "prensa@example.com", "apodo": ""})
    assert resp.status_code == 302
    sub = NewsletterSubscriber.objects.get(email="prensa@example.com")
    assert sub.status == NewsletterSubscriber.Status.PENDING


def test_subscribe_duplicate_email_is_idempotent(client):
    NewsletterSubscriber.objects.create(email="ya@example.com")
    resp = client.post(reverse("community:subscribe"), {"email": "ya@example.com", "apodo": ""})
    assert resp.status_code == 302
    assert NewsletterSubscriber.objects.filter(email="ya@example.com").count() == 1
