"""Las imágenes del HTML de autor solo se publican si son del propio sitio.

La CSP (`img-src 'self'`) bloquea las de otro sitio, que saldrían rotas, y pedirlas le contaría a ese
sitio cada visita. El saneado las quita enteras, con su `srcset` y con el enlace o la figura que solo
las contenían; las del propio sitio (una ruta relativa o el origen de SITE_URL) quedan. El panel lo
dice junto al cuerpo.
"""

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from apps.content.models import Article, Page
from apps.content.sanitize import clean_html
from tests.factories import admin_form_fields, make_published_article, soup

SITE = "https://repitentes.example"

# Direcciones que el navegador pediría a otro sitio, también las escritas para pasar por propias.
FOREIGN = [
    "https://tercero.example/foto.jpg",
    "http://repitentes.example/foto.jpg",
    "https://repitentes.example:8443/foto.jpg",
    "https://repitentes.example.tercero.example/foto.jpg",
    "https://repitentes.example@tercero.example/foto.jpg",
    "//tercero.example/foto.jpg",
    "///tercero.example/foto.jpg",
    " ///tercero.example/foto.jpg",
    "/\\tercero.example/foto.jpg",
    "https:\\\\tercero.example\\foto.jpg",
    " https://tercero.example/foto.jpg",
    "ht\ttps://tercero.example/foto.jpg",
    "https://tercero.example:puerto/foto.jpg",
    "",
]
OWN = [
    "/media/assets/foto.jpg",
    "media/assets/foto.jpg",
    "../media/assets/foto.jpg",
    "https://repitentes.example/media/assets/foto.jpg",
    "HTTPS://Repitentes.Example/media/assets/foto.jpg",
    "https://repitentes.example:443/media/assets/foto.jpg",
]


@pytest.fixture(autouse=True)
def _site_url(settings):
    settings.SITE_URL = SITE


@pytest.mark.parametrize("src", FOREIGN)
def test_an_image_from_another_site_is_removed_whole(src):
    html = clean_html(f'<p>Antes.</p><p><img src="{src}" alt="Foto de fuera"></p><p>Después.</p>')
    assert "<p>Antes.</p>" in html and "<p>Después.</p>" in html  # control: el resto queda
    assert "<img" not in html and "Foto de fuera" not in html


@pytest.mark.parametrize("src", OWN)
def test_an_image_from_the_site_is_kept(src):
    image = BeautifulSoup(clean_html(f'<p><img src="{src}" alt="Foto"></p>'), "html.parser").img
    assert (image["src"], image["alt"]) == (src, "Foto")


def test_srcset_never_brings_an_image_from_another_site():
    html = clean_html(
        '<img src="https://tercero.example/a.jpg" srcset="https://tercero.example/a2.jpg 2x" alt="a">'
        '<img srcset="https://tercero.example/b.jpg 1x" alt="b">'
        '<img src="/media/c.jpg" srcset="https://tercero.example/c2.jpg 2x" alt="c">'
    )
    images = BeautifulSoup(html, "html.parser").find_all("img")
    assert [image.attrs for image in images] == [{"src": "/media/c.jpg", "alt": "c"}]
    assert "tercero.example" not in html


def test_a_link_or_a_figure_that_only_held_the_image_goes_with_it():
    """Un enlace vacío no se ve, pero el teclado y el lector de pantalla se detienen en él; una
    figura vacía deja su margen. El pie y los enlaces con texto quedan."""
    html = clean_html(
        '<figure><a href="https://tercero.example/grande.jpg">'
        '<img src="https://tercero.example/a.jpg"></a></figure>'
        '<figure><img src="https://tercero.example/b.jpg"><figcaption>Pie que queda</figcaption>'
        "</figure>"
        '<p><a href="https://tercero.example/">Un enlace con texto</a></p>'
    )
    page = BeautifulSoup(html, "html.parser")
    assert page.find("img") is None
    assert [figure.get_text() for figure in page.find_all("figure")] == ["Pie que queda"]
    assert [link.get_text() for link in page.find_all("a")] == ["Un enlace con texto"]


def test_removing_images_is_idempotent():
    once = clean_html(
        '<figure><a href="/x"><img src="https://tercero.example/a.jpg"></a></figure>'
        '<p><img src="/media/b.jpg" alt="b"> y <img src="//tercero.example/c.jpg"></p>'
    )
    assert clean_html(once) == once
    assert '<img src="/media/b.jpg" alt="b">' in once  # control: la del sitio sigue


BODY = (
    "<p>Una foto del ensayo.</p>"
    '<figure><img src="https://tercero.example/foto.jpg" '
    'srcset="https://tercero.example/foto-2x.jpg 2x" alt="Foto de fuera"></figure>'
    '<figure><img src="/media/assets/ensayo.jpg" alt="Foto del sitio">'
    "<figcaption>Ensayo.</figcaption></figure>"
)


def _images_on(client, url):
    response = client.get(url)
    assert response.status_code == 200, url
    assert b"tercero.example" not in response.content, url
    body = BeautifulSoup(response.content, "html.parser").select_one("div.body")
    return [image["alt"] for image in body.find_all("img")]


@pytest.mark.django_db
def test_an_image_from_another_site_reaches_no_public_page(client):
    """Las dos fichas que pintan HTML de autor, con el cuerpo escrito sin pasar por `save()`
    (`update()`, loaddata, una migración): el filtro de salida también las quita."""
    article = make_published_article(slug="con-fotos", body="<p>x</p>")
    Article.objects.filter(pk=article.pk).update(body=BODY)
    page = Page.objects.create(slug="con-fotos", title="Con fotos", body="<p>x</p>")
    Page.objects.filter(pk=page.pk).update(body=BODY, status="published")
    for url in (article.get_absolute_url(), page.get_absolute_url()):
        assert _images_on(client, url) == ["Foto del sitio"], url


@pytest.mark.django_db
def test_saving_from_the_panel_keeps_only_the_images_of_the_site(client, editor):
    article = Article.objects.create(slug="pegado", title="Pegado", body="<p>x</p>", owner=editor)
    url = reverse("admin:content_article_change", args=[article.pk])
    client.force_login(editor)
    data = admin_form_fields(client.get(url).content, "article_form")
    data["body"] = BODY
    assert client.post(url, data).status_code == 302
    article.refresh_from_db()
    images = BeautifulSoup(article.body, "html.parser").find_all("img")
    assert [image["alt"] for image in images] == ["Foto del sitio"]


@pytest.mark.django_db
@pytest.mark.parametrize("form", ["admin:content_article_add", "admin:content_page_add"])
def test_the_panel_says_images_from_other_sites_are_not_published(client, editor, form):
    client.force_login(editor)
    page = soup(client, reverse(form))
    textarea = page.select_one("textarea#id_body")
    help_text = page.select_one(f"#{textarea['aria-describedby']}").get_text(" ", strip=True)
    assert help_text.startswith("Las imágenes de otros sitios no se publican")
