"""El nombre del sitio sale de una sola fuente.

Las páginas firman con el nombre del perfil del sitio (que se cambia en el panel) o, si está en
blanco, con el fijo, `SITE_NAME`: los dos los resuelve una vez el procesador de contexto, en
`site_name`. El 500, que se pinta sin procesadores ni base, y la cabecera del panel llevan el
fijo. Antes había tres respaldos distintos en las plantillas («Reseñas», el nombre del proyecto
anterior, y «Colectivo») y el 500 decía «Reseñas» escrito a mano.
"""

import json

import pytest
from django.conf import settings
from django.template import loader
from django.urls import reverse

from apps.showcase.models import SiteProfile
from tests.factories import make_published_article, soup

pytestmark = pytest.mark.django_db


def _name_everywhere(sopa):
    """Dónde firma una página con el nombre del sitio, lugar por lugar."""
    datos = [json.loads(s.string) for s in sopa.select('script[type="application/ld+json"]')]
    organizacion = next(dato for dato in datos if dato["@type"] == "Organization")
    return {
        "título": sopa.title.get_text().rsplit(" — ", 1)[-1],
        "og:site_name": sopa.select_one('meta[property="og:site_name"]')["content"],
        "sello": {s.get_text() for s in sopa.select(".brand-nombre")},
        "feeds": {
            link["title"].split(" — ")[0]
            for link in sopa.select('link[rel="alternate"][type="application/rss+xml"]')
        },
        "datos estructurados": organizacion["name"],
    }


def _signed_with(name):
    return {
        "título": name,
        "og:site_name": name,
        "sello": {name},
        "feeds": {name},
        "datos estructurados": name,
    }


@pytest.fixture
def profile():
    perfil = SiteProfile.load()
    perfil.name, perfil.tagline = "Colectivo Norte", "Poesía desde el desierto"
    perfil.save()
    return perfil


def test_every_page_signs_with_the_profile_name(client, profile):
    articulo = make_published_article(slug="un-texto", title="Un texto")
    for url in (reverse("content:poem_index"), articulo.get_absolute_url(), reverse("site:search")):
        sopa = soup(client, url)
        assert _name_everywhere(sopa) == _signed_with("Colectivo Norte"), url
    titulo = soup(client, articulo.get_absolute_url()).title.get_text()
    assert titulo == "Un texto — Colectivo Norte"
    # La portada no tiene título propio: el nombre y el lema, y el nombre en su h1.
    portada = soup(client, reverse("site:home"))
    assert portada.title.get_text() == "Colectivo Norte — Poesía desde el desierto"
    assert portada.select_one("h1 .sr-only").get_text() == "Colectivo Norte"
    assert soup(client, reverse("showcase:dossier")).h1.get_text() == "Colectivo Norte"


def test_a_profile_without_name_signs_with_the_fixed_one(client, profile):
    SiteProfile.objects.filter(pk=profile.pk).update(name="")
    sopa = soup(client, reverse("content:poem_index"))
    assert _name_everywhere(sopa) == _signed_with(settings.SITE_NAME)
    assert sopa.title.get_text() == f"Poemas — {settings.SITE_NAME}"
    assert soup(client, reverse("site:home")).select_one("h1 .sr-only").get_text() == (
        settings.SITE_NAME
    )
    assert soup(client, reverse("showcase:dossier")).h1.get_text() == settings.SITE_NAME


def test_the_500_page_carries_the_fixed_name_without_the_database(django_assert_num_queries):
    with django_assert_num_queries(0):
        html = loader.get_template("500.html").render()
    assert f"<title>Error del servidor — {settings.SITE_NAME}</title>" in html
    assert "Algo se rompió de nuestro lado" in html  # control: es la página del error


def test_the_admin_header_carries_the_fixed_name(client):
    sopa = soup(client, reverse("admin:login"))
    assert sopa.select_one("#site-name").get_text(strip=True) == (
        f"{settings.SITE_NAME} — Panel editorial"
    )
    assert sopa.title.get_text().endswith(f"| {settings.SITE_NAME}")


def test_a_new_site_profile_is_named_with_the_fixed_name():
    SiteProfile.objects.all().delete()
    assert SiteProfile.load().name == settings.SITE_NAME
