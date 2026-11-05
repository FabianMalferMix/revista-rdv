"""Lo que se muestra cuando falta una imagen (backlog UX, ticket 1.13)."""

import pytest
from django.urls import reverse

from apps.people.models import Contributor
from apps.people.templatetags.personas import iniciales
from tests.factories import make_image, make_publication

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
    """Una sola inicial en un círculo es el avatar por defecto de cualquier aplicación. El
    monograma va en la misma caja 4:5 que el retrato (ticket 3.6)."""
    Contributor.objects.create(
        slug="rocio", display_name="Rocío Carrasco", is_member=True, active=True
    )
    html = client.get(reverse("people:member_index")).content.decode()
    assert '<span class="retrato monograma" aria-hidden="true">RC</span>' in html


def test_a_member_with_a_portrait_shows_it_instead_of_the_monogram(client):
    portrait = make_image("retrato-con-foto", alt="Retrato de Con Foto")
    Contributor.objects.create(
        slug="con-foto", display_name="Con Foto", is_member=True, active=True, photo=portrait
    )
    html = client.get(reverse("people:member_index")).content.decode()
    assert 'class="retrato"' in html and "Retrato de Con Foto" in html
    assert "monograma" not in html


def test_una_publicacion_sin_cubierta_ensena_su_titulo(client):
    """El marcador era una caja con la palabra «LIBRO»: no decía de qué libro."""
    make_publication(slug="sin-cubierta", title="Cuaderno sin cubierta")
    html = client.get(reverse("showcase:publication_index")).content.decode()
    assert (
        '<span class="pub-cover-fallback" aria-hidden="true"><span>Cuaderno sin cubierta</span>'
        in html
    )
