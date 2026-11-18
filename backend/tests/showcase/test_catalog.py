"""La ficha de una publicación, con dónde comprarla, quiénes participan y su PDF; la página de
prensa, que enseña cada mención publicada con su cita; y las publicaciones de cada persona
(`Contributor.publications`)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.people.models import Contributor
from apps.showcase.models import PressMention, WhereToBuy
from tests.factories import make_publication  # noqa: E402

pytestmark = pytest.mark.django_db


def test_publication_detail_shows_stores_participants_and_pdf(client):
    member = Contributor.objects.create(
        slug="autora-pub", display_name="Autora Catálogo", is_member=True
    )
    pub = make_publication(
        slug="completa",
        title="Obra Completa",
        pdf=SimpleUploadedFile("obra.pdf", b"%PDF-1.4 fake"),
    )
    pub.participants.add(member)
    WhereToBuy.objects.create(publication=pub, label="Librería Aurora", url="https://example.com")
    resp = client.get(pub.get_absolute_url())
    assert b"Autora Cat\xc3\xa1logo" in resp.content
    assert b"Librer\xc3\xada Aurora" in resp.content
    assert b"Descargar PDF gratis" in resp.content


def test_press_index_lists_published_mentions(client):
    PressMention.objects.create(
        title="Nota Publicada", outlet="Diario Uno", quote="Voz nueva y necesaria."
    )
    PressMention.objects.create(title="Nota Oculta", outlet="Diario Dos", published=False)
    resp = client.get(reverse("showcase:press_index"))
    assert b"Nota Publicada" in resp.content
    assert b"Voz nueva y necesaria." in resp.content
    assert b"Nota Oculta" not in resp.content


def test_member_publications_reverse_relation():
    member = Contributor.objects.create(slug="con-obra", display_name="Con Obra")
    pub = make_publication(slug="suya", title="Su Libro")
    pub.participants.add(member)
    assert list(member.publications.all()) == [pub]
