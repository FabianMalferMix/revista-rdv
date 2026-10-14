"""Portada reordenada y archivo de textos (Lote UI-1)."""

import re

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db


def _pub(make_article, **kw):
    return make_article(status=EditorialStatus.PUBLISHED, published_at=timezone.now(), **kw)


def test_home_caps_articles_and_links_to_archive(client, make_article):
    for i in range(8):
        _pub(make_article, slug=f"t{i}", title=f"Texto {i}")
    resp = client.get(reverse("content:home"))
    assert resp.status_code == 200
    # Portada curada: los tres últimos textos (ticket 4.3; eran cinco). El resto vive en el
    # archivo, a un enlace.
    sopa = BeautifulSoup(resp.content, "html.parser")
    assert len(sopa.select(".home-obra li.article-card:not(.fila--poema)")) == 3
    assert sopa.select_one(f'.home-obra a[href="{reverse("content:text_archive")}"]') is not None


def test_text_archive_paginates_full_list(client, make_article):
    for i in range(15):
        _pub(make_article, slug=f"a{i}")
    resp = client.get(reverse("content:text_archive"))
    assert resp.status_code == 200
    page = resp.context["articles"]
    assert page.paginator.count == 15
    assert len(page.object_list) == 12
    page2 = client.get(reverse("content:text_archive") + "?page=2").context["articles"]
    assert len(page2.object_list) == 3


def test_home_shows_single_featured_recording_over_poem(client, make_poem):
    profile = SiteProfile.load()
    profile.featured_poem = make_poem(
        slug="p-dest",
        title="Poema Destacado",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    profile.featured_recording = Recording.objects.create(
        slug="r-dest",
        title="Registro Destacado",
        embed_url="https://youtu.be/xyz123ab",
        published=True,
    )
    profile.save()
    resp = client.get(reverse("content:home"))
    # Con ambos definidos, el registro manda: un solo destacado, sin apilar. El poema
    # puede salir en la lista de poemas (ticket 4.3), pero no como un segundo destacado.
    sopa = BeautifulSoup(resp.content, "html.parser")
    destacados = sopa.select(".featured")
    assert len(destacados) == 1
    assert "Registro Destacado" in destacados[0].get_text()
    assert "Poema Destacado" not in destacados[0].get_text()


def test_home_members_appear_before_texts(client, make_article):
    Contributor.objects.create(slug="m1", display_name="Integrante Uno", is_member=True)
    _pub(make_article, slug="tx", title="Texto Portada")
    content = client.get(reverse("content:home")).content
    assert content.index(b"Integrante Uno") < content.index(b"Texto Portada")


def test_home_hero_has_manifesto_and_stats(client):
    """El manifiesto, las cifras y el nombre como titular (ticket 4.2). Los años de trabajo
    ya no son una cifra: «desde 2019» va en la cejilla, con el lema."""
    profile = SiteProfile.load()
    profile.name = "Colectivo Norte"
    profile.tagline = "Poesía en voz alta."
    profile.manifesto = "Somos un colectivo que difunde la obra de sus integrantes."
    profile.founded_year = 2019
    profile.save()
    Contributor.objects.create(slug="m1", display_name="Integrante Uno", is_member=True)
    resp = client.get(reverse("content:home"))
    assert b"hero-manifesto" in resp.content
    assert b"hero-stats" in resp.content
    assert b"Poes\xc3\xada en voz alta." in resp.content
    assert b"desde 2019" in resp.content
    assert b'<h1 class="hero-nombre">Colectivo Norte</h1>' in resp.content


# ── Sello de convocatoria (backlog UX, ticket 3.2) ────────────────────────


def _convocatoria(abre, cierra, slug="conv"):
    from apps.submissions.models import Call

    ahora = timezone.now()
    return Call.objects.create(
        slug=slug, title="Convocatoria", opens_at=ahora + abre, closes_at=ahora + cierra
    )


def test_la_portada_lleva_el_sello_mientras_hay_una_convocatoria_abierta(client):
    from datetime import timedelta

    from django.utils.dateformat import format as formato

    abierta = _convocatoria(timedelta(days=-3), timedelta(days=12))
    html = client.get(reverse("content:home")).content.decode()
    sello = re.search(r'<a class="sello-convocatoria" href="([^"]+)">(.*?)</a>', html, re.S)
    assert sello, "con una convocatoria abierta, la portada no lleva el sello"
    assert sello.group(1) == reverse("submissions:submit")
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sello.group(2))).strip()
    cierre = formato(timezone.localtime(abierta.closes_at), r"j \d\e F")
    assert texto == f"Convocatoria abierta hasta el {cierre}"


def test_sin_convocatoria_abierta_no_hay_sello(client):
    from datetime import timedelta

    _convocatoria(timedelta(days=-40), timedelta(days=-5), slug="cerrada")
    _convocatoria(timedelta(days=5), timedelta(days=40), slug="futura")
    assert b"sello-convocatoria" not in client.get(reverse("content:home")).content


def test_el_destacado_va_sobre_el_papel_con_la_ficha_antes_del_reproductor(client):
    """El dueño del sitio descartó la banda de tinta del destacado. La ficha va antes que el
    reproductor en el HTML: se lee el título antes que el botón de reproducir."""
    profile = SiteProfile.load()
    profile.featured_recording = Recording.objects.create(
        slug="r-papel",
        title="Registro en papel",
        embed_url="https://youtu.be/xyz123ab",
        published=True,
    )
    profile.save()
    html = client.get(reverse("content:home")).content.decode()
    destacado = re.search(r'<section class="home-block featured">(.*?)</section>', html, re.S)
    assert destacado, "el destacado volvió a una banda"
    bloque = destacado.group(1)
    assert "band-in" not in bloque
    ficha, placa = bloque.index('class="featured-ficha"'), bloque.index("player-frame")
    enlace = bloque.index('class="meta featured-enlace"')
    assert ficha < placa < enlace, "orden: ficha, reproductor y enlace al índice"
