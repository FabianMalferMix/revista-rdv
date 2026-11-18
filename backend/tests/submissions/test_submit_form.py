"""El formulario para enviar una propuesta: su página responde, y el campo del archivo apunta
con aria-describedby a una ayuda que está en ella.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_submissions_route_stays_alive(client):
    assert client.get(reverse("submissions:submit")).status_code == 200


def test_submit_file_help_aria_reference_resolves(client):
    """El aria-describedby del input de archivo apunta a un id que EXISTE en el
    documento. Verificado con bs4."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(client.get(reverse("submissions:submit")).content, "html.parser")
    file_input = soup.find("input", {"type": "file"})
    described_by = file_input.get("aria-describedby")
    assert described_by, "el input de archivo debe declarar aria-describedby"
    assert soup.find(id=described_by) is not None, f"id '{described_by}' no existe en el HTML"
