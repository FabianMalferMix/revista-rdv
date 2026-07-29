"""La ficha de poema no publica grabaciones inéditas (hallazgo S-05).

Era el ÚNICO consumidor de `Recording` que no filtraba por estado de publicación:
`media/views.py`, `media/feeds.py` y el índice sí lo hacen. Un poema publicado con una
grabación `published=False` regalaba el audio y el enlace de embed en el HTML de una
página indexada —sin necesidad de adivinar nombres de archivo— y hacía que
«despublicar» un registro no lo retirase de la ficha.
"""

import pytest
from django.urls import reverse

from apps.content.models import EditorialStatus, Poem
from apps.media.models import Recording

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
        recording=recording,
    )
    return poem, recording


def test_la_ficha_no_expone_una_grabacion_no_publicada(client):
    poem, recording = _poema_con_registro(publicado=False)
    resp = client.get(reverse("content:poem_detail", args=[poem.slug]))
    assert resp.status_code == 200
    assert recording.embed_url.encode() not in resp.content
    assert b"Escuchar el poema" not in resp.content


def test_la_ficha_si_expone_una_grabacion_publicada(client):
    poem, recording = _poema_con_registro(publicado=True)
    resp = client.get(reverse("content:poem_detail", args=[poem.slug]))
    assert resp.status_code == 200
    assert recording.embed_url.encode() in resp.content
    assert b"Escuchar el poema" in resp.content


def test_despublicar_retira_la_grabacion_de_la_ficha():
    """Reversibilidad: quitar `published` debe retirarla de inmediato."""
    from django.test import Client

    poem, recording = _poema_con_registro(publicado=True)
    url = reverse("content:poem_detail", args=[poem.slug])
    assert recording.embed_url.encode() in Client().get(url).content

    recording.published = False
    recording.save(update_fields=["published"])
    assert recording.embed_url.encode() not in Client().get(url).content


def test_la_tarjeta_del_listado_no_anuncia_registros_ineditos(client):
    poem, _ = _poema_con_registro(publicado=False)
    resp = client.get(reverse("content:poem_index"))
    assert resp.status_code == 200
    assert b"con registro" not in resp.content


def test_published_recording_es_none_sin_grabacion():
    poem = Poem.objects.create(
        slug="sin-registro", title="Sin registro", body="x", status=EditorialStatus.PUBLISHED
    )
    assert poem.published_recording is None
