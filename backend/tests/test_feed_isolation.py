"""Los feeds no dependen del Host de la petición.

Las URL absolutas de los dos feeds (el canal, el enlace de cada ítem y el enclosure del
pódcast) salen de SITE_URL. Así una sola instancia de cada feed sirve a todos los hilos de
gunicorn sin guardar nada de la petición, y un Host distinto no cambia lo que reciben los
lectores de feeds ni las aplicaciones de pódcast.
"""

import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import resolve

from apps.content.models import EditorialStatus
from apps.media.models import Recording

pytestmark = pytest.mark.django_db
SITE = "https://revista.example.org"
HOSTS = ["uno.example.com", "dos.example.com"]


@pytest.fixture
def feeds_with_items(settings, make_article):
    settings.SITE_URL = SITE
    settings.ALLOWED_HOSTS = HOSTS
    make_article(status=EditorialStatus.PUBLISHED, slug="un-texto")
    Recording.objects.create(
        slug="lectura",
        title="Lectura",
        kind=Recording.Kind.AUDIO,
        published=True,
        file=SimpleUploadedFile("lectura.mp3", b"ID3\x04\x00\x00\x00"),
    )


@pytest.mark.parametrize("path", ["/feed/", "/feed/registros/"])
def test_the_feed_is_the_same_whatever_the_host(feeds_with_items, path):
    bodies = {Client(HTTP_HOST=host).get(path).content.decode() for host in HOSTS}
    assert len(bodies) == 1
    body = bodies.pop()
    assert not any(host in body for host in HOSTS)
    # Control positivo: los enlaces sí son absolutos, y del sitio.
    assert f"<link>{SITE}/" in body


def test_the_podcast_enclosure_comes_from_the_site_url(feeds_with_items):
    body = Client(HTTP_HOST=HOSTS[0]).get("/feed/registros/").content.decode()
    # La vista que entrega el audio solo mientras el registro está publicado.
    assert re.search(
        rf'<enclosure [^>]*url="{re.escape(SITE)}/archivo/registro/lectura/[^"]+\.mp3"', body
    )


@pytest.mark.parametrize("path", ["/feed/", "/feed/registros/"])
def test_both_feeds_are_registered_the_same_way(path):
    """Una instancia compartida: no guardan nada de la petición, así que no hay nada que
    se pisen dos hilos."""
    from django.contrib.syndication.views import Feed

    assert isinstance(resolve(path).func, Feed)
