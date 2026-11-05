"""Los PDF que se descargan tienen una dirección fija: /dossier.pdf y /publicacion/<slug>.pdf.

El dossier es lo que un gestor reenvía. El archivo nuevo no puede tomar el nombre del viejo hasta
que se confirma el guardado, así que una dirección con el nombre del archivo cambiaba con cada
reemplazo, y la de una publicación ya cambiaba por su nombre al azar.
"""

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.showcase.models import Publication, SiteProfile
from tests.factories import admin_form_fields

pytestmark = pytest.mark.django_db


def _pdf(name, text):
    return SimpleUploadedFile(name, b"%PDF-1.4 " + text, content_type="application/pdf")


def _body(response):
    # Leerlo entero cierra el archivo; el cliente de pruebas lo cierra sin cortar la base.
    return b"".join(response.streaming_content)


def _upload_in_panel(client, change_url, form_id, field, upload, capture):
    """Sube el archivo desde la ficha del panel, con el resto del formulario como estaba."""
    data = admin_form_fields(client.get(change_url).content.decode(), form_id)
    with capture(execute=True):
        response = client.post(change_url, {**data, field: upload})
    errors = BeautifulSoup(response.content, "html.parser").select(".errorlist li")
    assert response.status_code == 302, [e.get_text() for e in errors]


def _publication(published=True, **kwargs):
    return Publication.objects.create(
        slug="un-libro", title="Un libro", year=2024, published=published, **kwargs
    )


def _links(client, url):
    return [a["href"] for a in BeautifulSoup(client.get(url).content, "html.parser").select("a")]


def test_the_dossier_address_gives_the_new_pdf_after_a_replacement(
    admin_client, django_capture_on_commit_callbacks
):
    profile = SiteProfile.load()
    change = reverse("admin:showcase_siteprofile_change", args=[profile.pk])
    _upload_in_panel(
        admin_client,
        change,
        "siteprofile_form",
        "dossier_pdf",
        _pdf("dossier.pdf", b"uno"),
        django_capture_on_commit_callbacks,
    )
    first_name = SiteProfile.load().dossier_pdf.name
    assert _body(admin_client.get("/dossier.pdf")) == b"%PDF-1.4 uno"

    _upload_in_panel(
        admin_client,
        change,
        "siteprofile_form",
        "dossier_pdf",
        _pdf("dossier.pdf", b"dos"),
        django_capture_on_commit_callbacks,
    )
    assert SiteProfile.load().dossier_pdf.name != first_name, "the file kept its old name"
    response = admin_client.get("/dossier.pdf")
    assert _body(response) == b"%PDF-1.4 dos"
    assert response["Cache-Control"] == "no-cache"
    assert response["Content-Type"] == "application/pdf"


def test_the_publication_address_gives_the_new_pdf_after_a_replacement(
    client, editor, django_capture_on_commit_callbacks
):
    publication = _publication(pdf=_pdf("un-libro.pdf", b"primera"))
    client.force_login(editor)
    change = reverse("admin:showcase_publication_change", args=[publication.pk])
    url = publication.pdf_url()
    assert url == "/publicacion/un-libro.pdf"
    assert _body(client.get(url)) == b"%PDF-1.4 primera"

    _upload_in_panel(
        client,
        change,
        "publication_form",
        "pdf",
        _pdf("un-libro.pdf", b"segunda"),
        django_capture_on_commit_callbacks,
    )
    publication.refresh_from_db()
    assert publication.pdf_url() == url
    response = client.get(url)
    assert _body(response) == b"%PDF-1.4 segunda"
    assert response["Cache-Control"] == "no-cache"


def test_the_buttons_link_the_fixed_address(client):
    profile = SiteProfile.load()
    profile.dossier_pdf = _pdf("kit-de-prensa.pdf", b"kit")
    profile.save()
    publication = _publication(pdf=_pdf("un-libro.pdf", b"libro"))

    assert "/dossier.pdf" in _links(client, reverse("site:home"))
    assert "/dossier.pdf" in _links(client, reverse("showcase:dossier"))
    assert "/publicacion/un-libro.pdf" in _links(client, publication.get_absolute_url())
    for page in (reverse("site:home"), reverse("showcase:dossier")):
        assert not [href for href in _links(client, page) if href.startswith("/media/dossier/")]


def test_an_unpublished_publication_pdf_is_not_found(client, editor):
    publication = _publication(pdf=_pdf("un-libro.pdf", b"libro"))
    url = publication.pdf_url()
    assert _body(client.get(url)) == b"%PDF-1.4 libro"

    Publication.objects.filter(pk=publication.pk).update(published=False)
    assert client.get(url).status_code == 404
    client.force_login(editor)
    preview = client.get(url)
    assert _body(preview) == b"%PDF-1.4 libro"
    assert preview["Cache-Control"] == "private, no-store"


def test_without_a_pdf_the_fixed_addresses_are_not_found(client):
    publication = _publication()
    assert client.get("/dossier.pdf").status_code == 404
    assert client.get("/publicacion/un-libro.pdf").status_code == 404

    profile = SiteProfile.load()
    profile.dossier_pdf = _pdf("dossier.pdf", b"kit")
    profile.save()
    publication.pdf = _pdf("un-libro.pdf", b"libro")
    publication.save()
    assert _body(client.get("/dossier.pdf")) == b"%PDF-1.4 kit"
    assert _body(client.get("/publicacion/un-libro.pdf")) == b"%PDF-1.4 libro"


def test_behind_caddy_django_names_the_file_and_asks_to_revalidate(client, settings):
    settings.PROTECTED_MEDIA_ACCEL = True
    profile = SiteProfile.load()
    profile.dossier_pdf = _pdf("dossier.pdf", b"kit")
    profile.save()
    publication = _publication(pdf=_pdf("un-libro.pdf", b"libro"))

    for url, stored in (
        ("/dossier.pdf", profile.dossier_pdf.name),
        ("/publicacion/un-libro.pdf", publication.pdf.name),
    ):
        response = client.get(url)
        assert response.status_code == 200
        assert response["X-Accel-Redirect"] == f"/{stored}"
        assert response["Cache-Control"] == "no-cache"
        assert response.content == b""


def test_the_old_publication_address_redirects_to_the_fixed_one(client):
    publication = _publication(pdf=_pdf("un-libro.pdf", b"libro"))
    response = client.get("/archivo/publicacion/un-libro/3f2a9c1b.pdf")
    assert response.status_code == 301
    assert response["Location"] == publication.pdf_url()
