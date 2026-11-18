"""La sonda de vida, `/healthz/`, responde 200 con «ok»."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_healthz(client):
    resp = client.get(reverse("healthz"))
    assert resp.status_code == 200
    assert resp.content == b"ok"
