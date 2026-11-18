"""Borrar en el panel no se lleva por delante lo que algo usa.

Una imagen en uso, una persona que firma (también solo borradores) y una obra reseñada no se
pueden borrar: la confirmación enseña dónde se usan y qué hacer antes, y no borra nada. Lo que
nadie usa se borra como siempre. El listado de imágenes dice dónde se usa cada una.
"""

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.db.models import PROTECT, ProtectedError
from django.urls import reverse

from apps.content.models import Article
from apps.media.models import MediaAsset
from apps.people.models import Contributor
from apps.reviews.models import Work
from tests.factories import make_image, make_publication, publish

pytestmark = pytest.mark.django_db


def _article(title, **fields):
    return Article.objects.create(
        slug=title.lower().replace(" ", "-"), title=title, body="<p>x</p>", **fields
    )


def _confirmation(client, url):
    soup = BeautifulSoup(client.get(url).content, "html.parser")
    return soup.select_one("#deleted-objects").get_text(" ", strip=True), soup


def test_an_image_used_by_a_published_text_shows_its_uses_and_is_not_deleted(client, editor):
    cover = make_image("tapa")
    article = publish(_article("Cartografía del eco", cover_image=cover))
    unused = make_image("suelta")
    client.force_login(editor)

    url = reverse("admin:media_mediaasset_delete", args=[cover.pk])
    uses, soup = _confirmation(client, url)
    assert "Cartografía del eco" in uses
    assert "no se puede borrar" in soup.select_one("#content").get_text()
    assert not soup.select('#content input[type="submit"]')
    client.post(url, {"post": "yes"})
    assert MediaAsset.objects.filter(pk=cover.pk).exists()
    article.refresh_from_db()
    assert article.cover_image == cover

    client.post(reverse("admin:media_mediaasset_delete", args=[unused.pk]), {"post": "yes"})
    assert not MediaAsset.objects.filter(pk=unused.pk).exists()


def test_deleting_several_images_at_once_deletes_none_if_one_is_in_use(client, editor):
    cover, unused = make_image("tapa"), make_image("suelta")
    make_publication(slug="cuaderno", cover=cover)
    client.force_login(editor)
    response = client.post(
        reverse("admin:media_mediaasset_changelist"),
        {"action": "delete_selected", "_selected_action": [cover.pk, unused.pk], "post": "yes"},
    )
    assert "no se puede borrar" in response.content.decode()
    assert MediaAsset.objects.filter(pk__in=[cover.pk, unused.pk]).count() == 2


@pytest.mark.parametrize("published", [True, False])
def test_a_person_who_signs_a_text_is_not_deleted_and_is_asked_to_reassign_it(
    client, editor, published
):
    person = Contributor.objects.create(slug="ana", display_name="Ana Lira")
    article = _article("Correspondencias")
    article.authors.add(person)
    if published:
        publish(article)
    nobody = Contributor.objects.create(slug="nadie", display_name="Sin firma")
    client.force_login(editor)

    url = reverse("admin:people_contributor_delete", args=[person.pk])
    uses, soup = _confirmation(client, url)
    assert "Ana Lira firma «Correspondencias»" in uses
    assert "reasígnalos antes a otra firma" in soup.select_one("#content").get_text()
    client.post(url, {"post": "yes"})
    assert list(Article.objects.get(pk=article.pk).authors.all()) == [person]

    client.post(reverse("admin:people_contributor_delete", args=[nobody.pk]), {"post": "yes"})
    assert not Contributor.objects.filter(pk=nobody.pk).exists()


def test_a_reviewed_work_is_not_deleted_from_under_its_review():
    work = Work.objects.create(slug="antologia", title="Antología del margen")
    article = _article("Sobre la antología")
    article.reviewed_works.add(work)
    with pytest.raises(ProtectedError):
        work.delete()
    assert list(article.reviewed_works.all()) == [work]


def test_the_image_list_says_where_each_image_is_used(client, editor):
    cover, unused = make_image("tapa", alt="Tapa del cuaderno"), make_image("suelta", alt="Suelta")
    _article("Uno", cover_image=cover, og_image=cover)
    make_publication(slug="cuaderno", cover=cover)
    client.force_login(editor)
    soup = BeautifulSoup(
        client.get(reverse("admin:media_mediaasset_changelist")).content, "html.parser"
    )
    used_in = {
        row.select_one(".field-__str__").get_text(strip=True): row.select_one(
            ".field-used_in"
        ).get_text(strip=True)
        for row in soup.select("#result_list tbody tr")
    }
    assert used_in[str(cover)] == "artículo (2), publicación"
    assert used_in[str(unused)] == "—"


def test_every_reference_to_an_image_protects_it():
    """Retratos, tapas, afiches, logos, fotos de un evento y la obra de la portada: todas."""
    references = [
        f"{rel.related_model._meta.label}.{rel.field.name}"
        for rel in MediaAsset._meta.get_fields(include_hidden=True)
        if rel.is_relation and rel.auto_created and not rel.concrete
    ]
    assert len(references) >= 15
    assert [r for r in references if _on_delete(r) is not PROTECT] == []


def _on_delete(reference):
    label, field = reference.rsplit(".", 1)
    return apps.get_model(label)._meta.get_field(field).remote_field.on_delete
