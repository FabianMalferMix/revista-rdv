"""Un bot que llena el campo trampa del boletín recibe la respuesta neutra y no queda
suscrito.
"""

import pytest
from django.urls import reverse

from apps.community.models import NewsletterSubscriber
from apps.community.views import ALTA_NEUTRA

pytestmark = pytest.mark.django_db


def test_subscribe_honeypot_drops_bots(client):
    resp = client.post(
        reverse("community:subscribe"), {"email": "bot@spam.com", "apodo": "bot"}, follow=True
    )
    assert ALTA_NEUTRA in resp.content.decode()  # control: el bot recibe la respuesta neutra
    assert not NewsletterSubscriber.objects.filter(email="bot@spam.com").exists()
