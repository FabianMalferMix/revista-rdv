"""Lo que se muestra cuando falta una imagen (backlog UX, ticket 1.13)."""

import pytest
from django.urls import reverse

from apps.people.models import Contributor
from apps.people.templatetags.personas import iniciales
from tests.factories import make_publication

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("Fernanda Soto", "FS"),
        ("Camila", "C"),
        ("María José de la Fuente", "MF"),
        ("  ana   lópez ", "AL"),
        ("", ""),
        (None, ""),
    ],
)
def test_iniciales(nombre, esperado):
    assert iniciales(nombre) == esperado


def test_quien_no_tiene_retrato_lleva_su_monograma(client):
    """Una sola inicial en un círculo es el avatar por defecto de cualquier aplicación."""
    Contributor.objects.create(
        slug="rocio", display_name="Rocío Carrasco", is_member=True, active=True
    )
    html = client.get(reverse("people:member_index")).content.decode()
    assert '<span class="avatar avatar-fallback" aria-hidden="true">RC</span>' in html


def test_una_publicacion_sin_cubierta_ensena_su_titulo(client):
    """El marcador era una caja con la palabra «LIBRO»: no decía de qué libro."""
    make_publication(slug="sin-cubierta", title="Cuaderno sin cubierta")
    html = client.get(reverse("showcase:publication_index")).content.decode()
    assert (
        '<span class="pub-cover-fallback" aria-hidden="true"><span>Cuaderno sin cubierta</span>'
        in html
    )
