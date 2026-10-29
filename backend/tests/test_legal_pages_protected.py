"""Las páginas legales no se rompen desde el panel.

El pie de todas las páginas y el consentimiento del boletín y de los envíos enlazan a
`privacidad`, `cookies` y `terminos`. Desde el panel, la editora puede corregir su título y
su texto (los revisará un abogado), pero no cambiarles el slug, despublicarlas ni borrarlas,
tampoco con la acción en bloque. Cada caso lleva su control: una página corriente sí se
despublica y se borra.
"""

import pytest
from bs4 import BeautifulSoup
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.checks import run_checks
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.content.models import LEGAL_PAGES, Page, PublishStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def panel(client, editor, legal_pages):
    client.force_login(editor)
    return client


@pytest.fixture
def corriente():
    return Page.objects.create(
        slug="quienes-somos", title="Quiénes somos", body="<p>Somos</p>", status="published"
    )


def _formulario(panel, pagina):
    respuesta = panel.get(reverse("admin:content_page_change", args=[pagina.pk]))
    assert respuesta.status_code == 200
    return BeautifulSoup(respuesta.content, "html.parser").select_one("form#page_form")


def _guardar(panel, pagina, **cambios):
    datos = {
        "slug": pagina.slug,
        "title": pagina.title,
        "body": pagina.body,
        "status": pagina.status,
        "seo_title": "",
        "seo_description": "",
        **cambios,
    }
    return panel.post(reverse("admin:content_page_change", args=[pagina.pk]), datos)


@pytest.mark.parametrize("slug", LEGAL_PAGES)
def test_legal_page_form_keeps_text_editable_and_locks_slug_and_status(panel, slug):
    formulario = _formulario(panel, Page.objects.get(slug=slug))
    assert formulario.select_one('[name="title"]') is not None
    assert formulario.select_one('[name="body"]') is not None
    assert formulario.select_one('[name="slug"]') is None
    assert formulario.select_one('[name="status"]') is None
    assert "Página legal" in formulario.get_text()


def test_ordinary_page_form_offers_slug_and_status(panel, corriente):
    formulario = _formulario(panel, corriente)
    assert formulario.select_one('[name="slug"]') is not None
    assert formulario.select_one('[name="status"]') is not None
    assert "Página legal" not in formulario.get_text()


@pytest.mark.parametrize("slug", LEGAL_PAGES)
def test_editor_cannot_unpublish_or_rename_a_legal_page(panel, slug):
    pagina = Page.objects.get(slug=slug)
    respuesta = _guardar(panel, pagina, title="Título revisado", status="draft", slug="otra")
    assert respuesta.status_code == 302
    pagina.refresh_from_db()
    assert pagina.title == "Título revisado"
    assert (pagina.slug, pagina.status) == (slug, PublishStatus.PUBLISHED)
    assert panel.get(reverse("content:page_detail", args=[slug])).status_code == 200


def test_editor_can_unpublish_an_ordinary_page(panel, corriente):
    assert _guardar(panel, corriente, status="draft").status_code == 302
    corriente.refresh_from_db()
    assert corriente.status == PublishStatus.DRAFT


@pytest.mark.parametrize("slug", LEGAL_PAGES)
def test_editor_cannot_delete_a_legal_page(panel, slug):
    pagina = Page.objects.get(slug=slug)
    url = reverse("admin:content_page_delete", args=[pagina.pk])
    assert panel.get(url).status_code == 403
    assert panel.post(url, {"post": "yes"}).status_code == 403
    assert Page.objects.filter(slug=slug).exists()
    formulario = _formulario(panel, pagina)
    assert formulario.select_one("a.deletelink") is None


def test_editor_can_delete_an_ordinary_page(panel, corriente):
    assert _formulario(panel, corriente).select_one("a.deletelink") is not None
    url = reverse("admin:content_page_delete", args=[corriente.pk])
    assert panel.post(url, {"post": "yes"}).status_code == 302
    assert not Page.objects.filter(pk=corriente.pk).exists()


def test_bulk_delete_spares_the_legal_pages(panel, corriente):
    legales = list(Page.objects.filter(slug__in=LEGAL_PAGES).values_list("pk", flat=True))
    respuesta = panel.post(
        reverse("admin:content_page_changelist"),
        {
            "action": "delete_selected",
            ACTION_CHECKBOX_NAME: [*legales, corriente.pk],
            "post": "yes",
        },
    )
    assert respuesta.status_code == 403
    assert Page.objects.filter(slug__in=LEGAL_PAGES).count() == len(LEGAL_PAGES)
    respuesta = panel.post(
        reverse("admin:content_page_changelist"),
        {"action": "delete_selected", ACTION_CHECKBOX_NAME: [corriente.pk], "post": "yes"},
    )
    assert respuesta.status_code == 302
    assert not Page.objects.filter(pk=corriente.pk).exists()


def test_model_validation_refuses_unpublishing_a_legal_page(legal_pages, corriente):
    pagina = Page.objects.get(slug="privacidad")
    pagina.status = PublishStatus.DRAFT
    with pytest.raises(ValidationError):
        pagina.full_clean()
    corriente.status = PublishStatus.DRAFT
    corriente.full_clean()


def _legal_page_errors():
    return [e for e in run_checks(include_deployment_checks=True) if e.id == "content.E001"]


def test_deploy_check_passes_with_the_legal_pages_published(legal_pages):
    assert _legal_page_errors() == []


@pytest.mark.parametrize("slug", LEGAL_PAGES)
def test_deploy_check_fails_if_a_legal_page_is_missing_or_unpublished(legal_pages, slug):
    Page.objects.filter(slug=slug).update(status="draft")
    assert [slug in e.msg for e in _legal_page_errors()] == [True]
    Page.objects.filter(slug=slug).delete()
    assert [slug in e.msg for e in _legal_page_errors()] == [True]
