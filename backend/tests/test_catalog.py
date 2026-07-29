import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.people.models import Contributor
from apps.showcase.models import Partner, PressMention, WhereToBuy
from tests.factories import make_publication  # noqa: E402

pytestmark = pytest.mark.django_db


def test_publication_index_lists_published_only(client):
    make_publication(slug="visible", title="Plaquette Visible")
    make_publication(slug="oculta", title="Plaquette Oculta", published=False)
    resp = client.get(reverse("showcase:publication_index"))
    assert resp.status_code == 200
    assert b"Plaquette Visible" in resp.content
    assert b"Plaquette Oculta" not in resp.content


def test_publication_detail_404_when_unpublished(client):
    pub = make_publication(slug="privada", published=False)
    assert client.get(pub.get_absolute_url()).status_code == 404


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


def test_partner_index_lists_active_only(client):
    Partner.objects.create(name="Fondo Activo")
    Partner.objects.create(name="Fondo Inactivo", active=False)
    resp = client.get(reverse("showcase:partner_index"))
    assert b"Fondo Activo" in resp.content
    assert b"Fondo Inactivo" not in resp.content


def test_home_shows_catalog_press_and_partners(client):
    make_publication(slug="en-home", title="Plaquette En Portada", featured=True)
    PressMention.objects.create(title="n", outlet="Radio Cita", quote="Imprescindibles.")
    Partner.objects.create(name="Aliado En Portada")
    resp = client.get(reverse("content:home"))
    assert b"Plaquette En Portada" in resp.content
    assert b"Imprescindibles." in resp.content
    assert b"Aliado En Portada" in resp.content


def test_trayectoria_includes_publications_by_year(client):
    make_publication(slug="hist", title="Plaquette Histórica", year=2021)
    resp = client.get(reverse("agenda:trayectoria"))
    assert b"Plaquette Hist\xc3\xb3rica" in resp.content
    assert b"2021" in resp.content
    assert b"publicaci" in resp.content  # stats strip


def test_member_publications_reverse_relation():
    member = Contributor.objects.create(slug="con-obra", display_name="Con Obra")
    pub = make_publication(slug="suya", title="Su Libro")
    pub.participants.add(member)
    assert list(member.publications.all()) == [pub]
