"""Las direcciones y los identificadores de lo publicado no cambian.

Un enlace a un texto circula en notas de prensa, dossiers y redes; el GUID de un ítem es
lo que usan los lectores de feeds y las aplicaciones de pódcast para no repetirlo. Si
cambian, el enlace da 404 y el episodio se descarga otra vez.
"""

import re

import pytest
from django.contrib.admin import site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.test import Client
from django.utils import timezone

from apps.content.models import Article, EditorialStatus
from apps.media.models import Recording
from apps.people.models import Contributor
from config.feeds import FEED_GUID_AUTHORITY
from config.publishing import FrozenSlugAdminMixin

pytestmark = pytest.mark.django_db


def _guids(path, host="testserver"):
    response = Client(HTTP_HOST=host).get(path)
    assert response.status_code == 200
    return re.findall(r"<guid[^>]*>[^<]*</guid>", response.content.decode())


def _article(**extra):
    return Article.objects.create(
        title="Un texto",
        slug="un-texto",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        **extra,
    )


def _recording():
    return Recording.objects.create(
        title="Lectura en el puerto",
        slug="lectura-en-el-puerto",
        kind=Recording.Kind.AUDIO,
        file=SimpleUploadedFile("lectura.mp3", b"ID3", content_type="audio/mpeg"),
        published=True,
        published_at=timezone.now(),
    )


@pytest.mark.parametrize(
    ("path", "make", "kind"),
    [("/feed/", _article, "article"), ("/feed/registros/", _recording, "recording")],
)
def test_feed_guid_survives_a_new_slug_and_another_host(path, make, kind, settings):
    settings.ALLOWED_HOSTS = ["testserver", "otro.example.com"]
    piece = make()
    before = _guids(path)
    assert before == [
        f'<guid isPermaLink="false">tag:{FEED_GUID_AUTHORITY}:{kind}/{piece.pk}</guid>'
    ]

    type(piece).objects.filter(pk=piece.pk).update(slug="otra-direccion")
    assert _guids(path) == before
    assert _guids(path, host="otro.example.com") == before


def test_published_text_shows_its_slug_read_only_in_the_panel(client, editor, make_article):
    published = make_article(status=EditorialStatus.PUBLISHED, slug="ya-publicado")
    draft = make_article(slug="todavia-borrador")
    client.force_login(editor)

    html = client.get(f"/admin/content/article/{published.pk}/change/").content.decode()
    assert 'name="slug"' not in html
    assert '<div class="readonly">ya-publicado</div>' in html
    # Y en su sitio, antes del título, no al final con los demás campos de solo lectura.
    assert html.index("field-slug") < html.index("field-title")
    # Control positivo: mientras no es pública, la dirección se puede editar.
    html = client.get(f"/admin/content/article/{draft.pk}/change/").content.decode()
    assert 'name="slug"' in html


# Los modelos con slug y ficha pública, y los que tienen slug sin ficha. Un modelo nuevo
# con slug tiene que entrar en una de las dos listas: así se decide si su dirección se
# congela, en vez de olvidarlo.
SLUG_WITH_PUBLIC_PAGE = {
    "content.article",
    "content.poem",
    "content.section",
    "content.tag",
    "content.collection",
    "content.page",
    "media.recording",
    "agenda.event",
    "showcase.publication",
    "people.contributor",
    "reviews.work",
    "reviews.publisher",
    "reviews.bookauthor",
}
SLUG_WITHOUT_PUBLIC_PAGE = {"submissions.call"}


def test_every_admin_with_a_public_slug_freezes_it():
    with_slug = {
        model._meta.label_lower
        for model in site._registry
        if any(isinstance(field, models.SlugField) for field in model._meta.fields)
    }
    assert with_slug == SLUG_WITH_PUBLIC_PAGE | SLUG_WITHOUT_PUBLIC_PAGE
    for model, model_admin in site._registry.items():
        if model._meta.label_lower in SLUG_WITH_PUBLIC_PAGE:
            assert isinstance(model_admin, FrozenSlugAdminMixin), model._meta.label_lower


def test_former_member_page_redirects_to_the_collaborator_page(client, make_article):
    person = Contributor.objects.create(slug="ex-integrante", display_name="Ex Integrante")
    article = make_article(status=EditorialStatus.PUBLISHED)
    article.authors.add(person)

    response = client.get("/integrante/ex-integrante/")
    assert response.status_code == 302
    assert response["Location"] == "/colaborador/ex-integrante/"
    assert client.get(response["Location"]).status_code == 200


def test_member_page_of_someone_without_a_public_page_stays_404(client):
    Contributor.objects.create(slug="sin-ficha", display_name="Sin Ficha")
    assert client.get("/integrante/sin-ficha/").status_code == 404
    # Control positivo: una integrante sí tiene su ficha en esa dirección.
    Contributor.objects.create(slug="con-ficha", display_name="Con Ficha", is_member=True)
    assert client.get("/integrante/con-ficha/").status_code == 200
