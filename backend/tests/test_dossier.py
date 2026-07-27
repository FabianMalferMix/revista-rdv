import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.people.models import Contributor
from apps.showcase.models import Partner, PressMention, Publication, SiteProfile

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile(db):
    p = SiteProfile.load()
    p.name = "Colectivo Prueba"
    p.tagline = "Poesía que camina."
    p.manifesto = "Somos un colectivo dedicado a la palabra."
    p.booking_email = "gestion@example.com"
    p.founded_year = 2019
    p.save()
    return p


def test_dossier_aggregates_everything(client, profile):
    Contributor.objects.create(
        slug="poeta-dossier",
        display_name="Poeta Dossier",
        is_member=True,
        short_bio="Escribe y gestiona.",
    )
    Publication.objects.create(
        slug="pub-dossier", title="Plaquette Dossier", published=True, year=2022
    )
    PressMention.objects.create(title="n", outlet="Medio Dossier", quote="Notables.")
    Partner.objects.create(name="Fondo Dossier")

    resp = client.get(reverse("showcase:dossier"))
    assert resp.status_code == 200
    for fragment in [
        b"Colectivo Prueba",
        b"Somos un colectivo dedicado a la palabra.",
        b"Poeta Dossier",
        b"Plaquette Dossier",
        b"Notables.",
        b"Fondo Dossier",
        b"gestion@example.com",
        b"window.print()",
    ]:
        assert fragment in resp.content


def test_dossier_excludes_unpublished_publication(client, profile):
    Publication.objects.create(slug="oculta-d", title="Oculta Dossier", published=False)
    resp = client.get(reverse("showcase:dossier"))
    assert b"Oculta Dossier" not in resp.content


def test_home_cta_links_to_dossier_page_without_pdf(client, profile):
    resp = client.get(reverse("content:home"))
    assert b"Descargar dossier" in resp.content
    assert reverse("showcase:dossier").encode() in resp.content
    assert b"Contacto de gesti\xc3\xb3n" in resp.content


def test_home_cta_prefers_uploaded_pdf(client, profile):
    profile.dossier_pdf = SimpleUploadedFile("dossier.pdf", b"%PDF-1.4 fake")
    profile.save()
    resp = client.get(reverse("content:home"))
    assert profile.dossier_pdf.url.encode() in resp.content


def test_dossier_page_offers_pdf_download_when_uploaded(client, profile):
    profile.dossier_pdf = SimpleUploadedFile("dossier2.pdf", b"%PDF-1.4 fake")
    profile.save()
    resp = client.get(reverse("showcase:dossier"))
    assert b"Descargar PDF maquetado" in resp.content
