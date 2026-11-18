"""La ficha de poema no publica grabaciones inéditas.

Si la grabación de un poema publicado no está publicada, el HTML de la ficha (una página
indexada) no lleva ni su enlace ni el del proveedor, y despublicar un registro lo retira de la
ficha.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus, Poem
from apps.media.models import Recording
from tests.factories import soup

pytestmark = pytest.mark.django_db


def _poema_con_registro(*, publicado):
    recording = Recording.objects.create(
        slug="inedito",
        title="Registro inédito",
        kind=Recording.Kind.AUDIO,
        embed_url="https://vimeo.com/999999",
        published=publicado,
    )
    poem = Poem.objects.create(
        slug="umbral",
        title="Umbral",
        body="verso",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        recording=recording,
    )
    return poem, recording


def test_la_ficha_no_expone_una_grabacion_no_publicada(client):
    poem, recording = _poema_con_registro(publicado=False)
    resp = client.get(reverse("content:poem_detail", args=[poem.slug]))
    assert resp.status_code == 200
    assert recording.embed_url.encode() not in resp.content
    assert recording.get_absolute_url().encode() not in resp.content
    assert b"Escuchar el poema" not in resp.content


def test_despublicar_retira_la_grabacion_de_la_ficha():
    """Reversibilidad: quitar `published` debe retirarla de inmediato."""
    from django.test import Client

    poem, recording = _poema_con_registro(publicado=True)
    url = reverse("content:poem_detail", args=[poem.slug])
    assert recording.get_absolute_url().encode() in Client().get(url).content

    recording.published = False
    recording.save(update_fields=["published"])
    page = soup(Client(), url)
    assert page.select_one("h1").get_text(strip=True) == "Umbral"  # control: la ficha sigue
    assert recording.get_absolute_url() not in str(page)


def test_la_tarjeta_del_listado_no_anuncia_registros_ineditos(client):
    poem, _ = _poema_con_registro(publicado=False)
    resp = client.get(reverse("content:poem_index"))
    assert resp.status_code == 200
    assert b"con registro" not in resp.content


def test_published_recording_es_none_sin_grabacion():
    poem = Poem.objects.create(
        slug="sin-registro",
        title="Sin registro",
        body="x",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    assert poem.published_recording is None
