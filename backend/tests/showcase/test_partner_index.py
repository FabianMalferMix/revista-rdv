"""La página de aliados se titula «Aliados», como los enlaces que llevan a ella."""

import pytest
from django.urls import reverse

from tests.factories import soup

pytestmark = pytest.mark.django_db


def test_aliados_se_titula_como_el_enlace_que_lleva_a_ella(client):
    """El pie, la sub-fila de «Prensa y gestión» y el cierre de la portada la llaman
    «Aliados», y su título también: la bajada ya habla de los fondos."""
    assert soup(client, reverse("showcase:partner_index")).h1.get_text(strip=True) == "Aliados"
