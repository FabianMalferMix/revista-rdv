"""Ninguna URL absoluta depende del Host de la petición.

Con SITE_URL definido, pedir una página, el sitemap, robots o los feeds con otro Host no
cambia nada: canonical, og:url, la imagen para compartir, el JSON-LD, el dominio que imprime
el dossier y los enlaces del sitemap y de los feeds salen de SITE_URL. Un Host distinto (www,
una IP, un proxy mal configurado) no puede cambiar la identidad de una página.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.content.models import EditorialStatus
from apps.media.models import Recording
from apps.showcase.models import SiteProfile
from tests.factories import make_article, make_event, make_image

pytestmark = pytest.mark.django_db
SITE = "https://revista.example.org"
OTHER_HOST = "otro.example.com"


@pytest.fixture
def site(settings):
    settings.SITE_URL = SITE
    settings.ALLOWED_HOSTS = ["testserver", OTHER_HOST]
    perfil = SiteProfile.load()
    perfil.og_image = make_image("portada")
    perfil.save()
    article = make_article(status=EditorialStatus.PUBLISHED, slug="un-texto")
    event = make_event(slug="un-recital")
    Recording.objects.create(
        slug="lectura",
        title="Lectura",
        kind=Recording.Kind.AUDIO,
        published=True,
        file=SimpleUploadedFile("lectura.mp3", b"ID3\x04\x00\x00\x00"),
    )
    return [
        "/",
        article.get_absolute_url(),
        event.get_absolute_url() + "?utm_source=boletin&fbclid=abc",
        "/dossier/",
        "/robots.txt",
        "/sitemap.xml",
        "/feed/",
        "/feed/registros/",
    ]


def test_no_absolute_url_follows_the_host_of_the_request(site):
    client = Client(HTTP_HOST=OTHER_HOST)
    for path in site:
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.content.decode()
        assert OTHER_HOST not in body, path
        # Control positivo: la respuesta sí lleva URL absolutas, y del sitio.
        assert "revista.example.org" in body, path


def test_event_json_ld_names_the_canonical_url(site, client):
    """El JSON-LD del evento usa la dirección canónica: sin la query string ni su &amp;."""
    html = client.get("/evento/un-recital/?utm_source=boletin&fbclid=abc").content.decode()
    assert f'"url": "{SITE}/evento/un-recital/"' in html
    assert "fbclid" not in html
