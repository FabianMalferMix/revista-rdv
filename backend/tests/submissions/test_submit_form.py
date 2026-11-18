"""El formulario para enviar una propuesta: el campo del archivo apunta con aria-describedby a
una ayuda que está en ella, y un envío crea la propuesta, salvo el que llena el campo trampa,
que se descarta con el mismo agradecimiento.
"""

import pytest
from django.urls import reverse

from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db


def test_submit_file_help_aria_reference_resolves(client):
    """El aria-describedby del input de archivo apunta a un id que EXISTE en el
    documento. Verificado con bs4."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(client.get(reverse("submissions:submit")).content, "html.parser")
    file_input = soup.find("input", {"type": "file"})
    described_by = file_input.get("aria-describedby")
    assert described_by, "el input de archivo debe declarar aria-describedby"
    assert soup.find(id=described_by) is not None, f"id '{described_by}' no existe en el HTML"


def test_submission_post_creates(client):
    resp = client.post(
        reverse("submissions:submit"),
        data={
            "author_name": "Ana",
            "author_email": "ana@example.com",
            "type": "resena",
            "title": "Mi propuesta",
            "body": "cuerpo",
            "apodo": "",
        },
    )
    assert resp.status_code == 302
    assert Submission.objects.filter(title="Mi propuesta").exists()


def test_submission_honeypot_is_dropped(client):
    resp = client.post(
        reverse("submissions:submit"),
        data={
            "author_name": "Bot",
            "author_email": "bot@spam.com",
            "type": "otro",
            "title": "spam",
            "body": "x",
            "apodo": "bot",
        },
    )
    # Control: el bot recibe el mismo agradecimiento que un envío de verdad.
    assert resp.status_code == 302 and resp["Location"] == reverse("submissions:submit_thanks")
    assert not Submission.objects.filter(title="spam").exists()
