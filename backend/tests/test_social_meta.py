"""La imagen para compartir: cada ficha emite la misma combinación de `og:image` y
`twitter:card`, según tenga imagen propia o no.

Con imagen propia, esa; sin ella, la del perfil del sitio; en los dos casos, la tarjeta
grande. Sin ninguna, no hay `og:image` y la tarjeta es la pequeña. Antes, el texto, el
evento y la publicación dejaban la tarjeta pequeña aunque usaran la imagen del perfil, y el
texto ignoraba la imagen para compartir que se elige en el panel.
"""

import json

import pytest
from bs4 import BeautifulSoup
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.showcase.models import SiteProfile
from tests.factories import make_event, make_image, make_publication, make_recording

pytestmark = pytest.mark.django_db

PUBLICADO = {"status": EditorialStatus.PUBLISHED, "published_at": timezone.now()}


@pytest.fixture
def ficha(make_article, make_poem):
    """`ficha(tipo, imagen)`: una pieza publicada de ese tipo, con `imagen` como propia."""

    def _ficha(tipo, imagen):
        if tipo == "texto":
            return make_article(og_image=imagen, **PUBLICADO)
        if tipo == "poema":
            return make_poem(og_image=imagen, **PUBLICADO)
        if tipo == "actividad":
            return make_event(poster=imagen)
        if tipo == "publicacion":
            return make_publication(cover=imagen)
        return make_recording(poster=imagen)

    return _ficha


def _perfil_con_imagen(imagen):
    perfil = SiteProfile.load()
    perfil.og_image = imagen
    perfil.save()


def _url(imagen):
    return f"http://testserver{imagen.file.url}"


def _sopa(client, url):
    respuesta = client.get(url)
    assert respuesta.status_code == 200
    return BeautifulSoup(respuesta.content, "html.parser")


def _social(sopa):
    imagen = sopa.select_one('meta[property="og:image"]')
    tarjeta = sopa.select_one('meta[name="twitter:card"]')
    return (imagen["content"] if imagen else None, tarjeta["content"])


@pytest.mark.parametrize("tipo", ["texto", "poema", "actividad", "publicacion", "registro"])
def test_detail_page_shares_its_own_image_or_the_site_one(client, ficha, tipo):
    del_sitio = make_image("sitio")
    _perfil_con_imagen(del_sitio)
    propia = make_image(f"propia-{tipo}")
    con_imagen, sin_imagen = ficha(tipo, propia), ficha(tipo, None)

    grande = "summary_large_image"
    assert _social(_sopa(client, con_imagen.get_absolute_url())) == (_url(propia), grande)
    assert _social(_sopa(client, sin_imagen.get_absolute_url())) == (_url(del_sitio), grande)
    _perfil_con_imagen(None)
    assert _social(_sopa(client, sin_imagen.get_absolute_url())) == (None, "summary")


def test_any_page_shares_the_site_image(client):
    _perfil_con_imagen(make_image("sitio"))
    imagen, tarjeta = _social(_sopa(client, "/"))
    assert imagen.endswith(".jpg") and tarjeta == "summary_large_image"
    _perfil_con_imagen(None)
    assert _social(_sopa(client, "/")) == (None, "summary")


def test_article_prefers_its_share_image_over_its_cover(client, make_article):
    portada, para_compartir = make_image("portada"), make_image("compartir")
    con_las_dos = make_article(cover_image=portada, og_image=para_compartir, **PUBLICADO)
    solo_portada = make_article(cover_image=portada, **PUBLICADO)
    assert _social(_sopa(client, con_las_dos.get_absolute_url()))[0] == _url(para_compartir)
    assert _social(_sopa(client, solo_portada.get_absolute_url()))[0] == _url(portada)


def _ld_image(sopa, tipo):
    datos = [json.loads(s.string) for s in sopa.select('script[type="application/ld+json"]')]
    return next(d for d in datos if d.get("@type") == tipo).get("image")


@pytest.mark.parametrize("tipo,esquema", [("texto", "Article"), ("actividad", "Event")])
def test_json_ld_uses_the_same_image(client, ficha, tipo, esquema):
    del_sitio = make_image("sitio")
    _perfil_con_imagen(del_sitio)
    propia = make_image("propia")
    assert _ld_image(_sopa(client, ficha(tipo, propia).get_absolute_url()), esquema) == _url(propia)
    assert _ld_image(_sopa(client, ficha(tipo, None).get_absolute_url()), esquema) == _url(
        del_sitio
    )
