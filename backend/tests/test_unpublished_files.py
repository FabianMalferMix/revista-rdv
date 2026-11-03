"""Lo despublicado deja de servirse: el audio de un registro y el PDF de una publicación
solo salen mientras su pieza es pública.

Antes los servía Caddy desde /media/ sin preguntar: despublicar ocultaba la ficha, pero el
archivo seguía respondiendo a quien tuviera la URL, que el feed de pódcast ya había
repartido.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.media.models import Recording
from apps.showcase.models import Publication

pytestmark = pytest.mark.django_db
AUDIO = b"ID3 una lectura en el puerto"


def _recording(published=True):
    return Recording.objects.create(
        slug="lectura",
        title="Lectura",
        kind=Recording.Kind.AUDIO,
        file=SimpleUploadedFile("lectura-en-el-puerto.mp3", AUDIO, content_type="audio/mpeg"),
        published=published,
        published_at=timezone.now(),
    )


def _body(response):
    # Leerlo entero cierra el archivo; el cliente de pruebas lo cierra sin cortar la base.
    return b"".join(response.streaming_content)


def _status(client, url):
    response = client.get(url)
    if response.streaming:
        _body(response)
    return response.status_code


def test_a_published_recording_serves_its_audio(client):
    recording = _recording()
    response = client.get(recording.file_url())
    assert response.status_code == 200
    assert _body(response) == AUDIO


def test_unpublishing_a_recording_stops_serving_its_audio(client):
    recording = _recording()
    url = recording.file_url()
    assert _status(client, url) == 200
    Recording.objects.filter(pk=recording.pk).update(published=False)
    assert _status(client, url) == 404


def test_the_team_still_hears_an_unpublished_recording(client, editor):
    recording = _recording(published=False)
    client.force_login(editor)
    response = client.get(recording.file_url())
    assert _body(response) == AUDIO
    assert response["Cache-Control"] == "private, no-store"


def test_a_replaced_file_is_not_served_by_its_old_name(client):
    recording = _recording()
    old_url = recording.file_url()
    recording.file = SimpleUploadedFile(
        "otra-toma.mp3", b"ID3 otra toma", content_type="audio/mpeg"
    )
    recording.save()
    assert _status(client, old_url) == 404
    assert _status(client, recording.file_url()) == 200


def test_behind_caddy_django_only_names_the_file(client, settings):
    settings.PROTECTED_MEDIA_ACCEL = True
    recording = _recording()
    response = client.get(recording.file_url())
    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == f"/{recording.file.name}"
    assert response.content == b""
    Recording.objects.filter(pk=recording.pk).update(published=False)
    assert _status(client, recording.file_url()) == 404


def test_the_publication_pdf_follows_the_same_rule(client):
    publication = Publication.objects.create(
        slug="un-libro",
        title="Un libro",
        year=2024,
        published=True,
        pdf=SimpleUploadedFile(
            "un-libro.pdf", b"%PDF-1.4 un libro", content_type="application/pdf"
        ),
    )
    assert _status(client, publication.pdf_url()) == 200
    Publication.objects.filter(pk=publication.pk).update(published=False)
    assert _status(client, publication.pdf_url()) == 404


def test_uploads_get_random_names():
    """El nombre original suele ser el slug: con él, se adivinaba la dirección del archivo."""
    name = _recording().file.name
    assert "lectura" not in name
    assert name.startswith("recordings/") and name.endswith(".mp3")


def test_the_player_and_the_podcast_point_to_the_checked_url(client):
    recording = _recording()
    assert (
        f'src="{recording.file_url()}"' in client.get(recording.get_absolute_url()).content.decode()
    )
    assert recording.file_url() in client.get("/feed/registros/").content.decode()
