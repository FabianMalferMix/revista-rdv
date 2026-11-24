"""Los textos que el panel de Django arma por su cuenta, dichos como el resto del panel.

Un dato repetido entre las filas de un inline se nombra por el rótulo de su campo, «Agregar …
adicional» lleva el nombre del modelo en minúscula, bajo un selector doble no sale la ayuda de la
lista de selección múltiple, y una cuenta de solo lectura se lee por su nombre, sin enlace a su
ficha, que solo abre quien administra las cuentas. Lo arma config/panel.py.
"""

import json
import re

import pytest
from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from apps.content.models import ArticleContributor, EditorialNote
from apps.media.models import MediaAsset
from apps.people.models import Contributor
from apps.submissions.models import Submission
from config.panel import PanelWordingMixin
from tests.factories import admin_form_fields, make_article, make_image, soup

pytestmark = pytest.mark.django_db


def _texts(elements):
    return [" ".join(element.get_text().split()) for element in elements]


def _account(username, group):
    account = get_user_model().objects.create_user(username, password="pw", is_staff=True)
    account.groups.add(group)
    return account


def _request(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


# ── Un dato repetido entre las filas de un inline ─────────


def test_a_repeated_row_names_its_field(client, editor):
    """Dos filas de la autoría de un artículo con la misma persona."""
    article = make_article(owner=editor)
    lucia = Contributor.objects.create(slug="lucia-prado", display_name="Lucía Prado")
    ArticleContributor.objects.create(article=article, contributor=lucia)
    client.force_login(editor)
    url = reverse("admin:content_article_change", args=[article.pk])
    data = admin_form_fields(client.get(url).content, "article_form")
    # La fila en blanco del inline, con la persona que ya firma.
    data["articlecontributor_set-1-contributor"] = str(lucia.pk)
    response = client.post(url, data)
    assert response.status_code == 200, "el formulario se guardó: no había nada repetido"
    group = BeautifulSoup(response.content, "html.parser").select_one(
        "#articlecontributor_set-group"
    )
    assert _texts(group.select("ul.errorlist.nonform li")) == [
        "Por favor, corrija el dato duplicado para colaborador."
    ]


def test_every_inline_names_a_repeated_row_by_its_labels():
    """El aviso de Django nombra los campos por su nombre interno, «article y contributor», y
    entre ellos la pieza de la ficha, que es la misma en todas las filas."""
    request = _request(get_user_model().objects.create_superuser("raiz", password="pw"))
    seen, wrong = set(), []
    for model_admin in admin.site._registry.values():
        for formset_class, _inline in model_admin.get_formsets_with_inlines(request):
            formset = formset_class()
            meta = formset.model._meta
            own_key = formset.fk.name if hasattr(formset, "fk") else None
            unique_checks, _date_checks = formset.model()._get_unique_checks(
                include_meta_constraints=True
            )
            for _model, check in unique_checks:
                if check == (meta.pk.name,):
                    continue
                seen.add(meta.label)
                message = formset.get_unique_error_message(check)
                labels = [str(meta.get_field(name).verbose_name) for name in check]
                own = [str(meta.get_field(own_key).verbose_name)] if own_key in check else []
                if (
                    any(re.search(rf"\b{name}\b", message) for name in check)
                    or any(label in message for label in own)
                    or not all(label in message for label in labels if label not in own)
                ):
                    wrong.append(f"{meta.label} {check}: «{message}»")
    # Control: llega a los siete inlines que no admiten dos filas iguales.
    assert {
        "content.ArticleContributor",
        "content.ReviewedWork",
        "content.PoemContributor",
        "content.CollectionArticle",
        "content.CollectionPoem",
        "agenda.EventPhoto",
        "people.SocialLink",
    } <= seen, seen
    assert not wrong, "avisos que no nombran los campos por su rótulo: " + ", ".join(wrong)


# ── Los textos de Django a media frase ────────────────────


def test_adding_a_row_names_the_model_in_lowercase(client, editor):
    """Django le pone mayúscula al modelo: «Agregar Nota editorial adicional.»."""
    article = make_article(owner=editor)
    client.force_login(editor)
    page = soup(client, reverse("admin:content_article_change", args=[article.pk]))
    texts = {
        group["id"]: json.loads(group["data-inline-formset"])["options"]["addText"]
        for group in page.select("[data-inline-formset]")
    }
    assert texts == {
        "articlecontributor_set-group": "Agregar autoría de artículo adicional.",
        "reviewed_work_links-group": "Agregar obra reseñada adicional.",
        "content-editorialnote-content_type-object_id-group": "Agregar nota editorial adicional.",
        "content-editorialtransition-content_type-object_id-group": (
            "Agregar transición editorial adicional."
        ),
    }


def test_a_double_selector_does_not_ask_to_hold_control(client, editor):
    """Mantener presionado «Control» es para la lista de selección múltiple: en el selector
    doble se marca y se pulsa la flecha."""
    client.force_login(editor)
    page = soup(client, reverse("admin:content_article_add"))
    # Control: las etiquetas se eligen en un selector doble.
    assert "selectfilter" in page.select_one("select#id_tags")["class"]
    assert "Mantenga presionado" not in page.get_text()


def test_the_account_selectors_keep_their_own_help(client, groups):
    """Los grupos y los permisos de una cuenta, y los de un grupo, también se eligen en
    selectores dobles: su ayuda sigue, sin la de mantener presionado «Control»."""
    account = _account("admin_test", groups["admin"])
    client.force_login(account)
    user_page = soup(client, reverse("admin:auth_user_change", args=[account.pk]))
    assert _texts(user_page.select("#id_groups_helptext, #id_user_permissions_helptext")) == [
        "Los grupos a los que pertenece este usuario. Un usuario tendrá todos los permisos "
        "asignados a cada uno de sus grupos.",
        "Permisos específicos para este usuario.",
    ]
    group_page = soup(client, reverse("admin:auth_group_add"))
    assert "selectfilter" in group_page.select_one("select#id_permissions")["class"]
    assert "Mantenga presionado" not in user_page.get_text() + group_page.get_text()


def test_every_admin_with_inlines_or_double_selectors_says_them_like_the_panel():
    concerned = {
        model._meta.label: model_admin
        for model, model_admin in admin.site._registry.items()
        if model_admin.inlines or model_admin.filter_horizontal or model_admin.filter_vertical
    }
    # Control: llega a las fichas de los textos, de las cuentas y de los grupos.
    assert {"content.Article", "auth.User", "auth.Group"} <= set(concerned), sorted(concerned)
    missing = sorted(
        label
        for label, model_admin in concerned.items()
        if not isinstance(model_admin, PanelWordingMixin)
    )
    assert not missing, "fichas con los textos de Django: " + ", ".join(missing)


# ── Las cuentas se leen por su nombre ─────────────────────


def _note_by_another_editor(groups, editor, autor):
    other = _account("editora_dos", groups["editor"])
    article = make_article(owner=autor)
    EditorialNote.objects.create(item=article, author=other, body="Falta la fecha del recital.")
    url = reverse("admin:content_article_change", args=[article.pk])
    return editor, url, "tr.has_original td.field-author_name", "editora_dos"


def _image_uploaded_by_an_author(groups, editor, autor):
    asset = make_image("retrato")
    MediaAsset.objects.filter(pk=asset.pk).update(uploaded_by=autor)
    url = reverse("admin:media_mediaasset_change", args=[asset.pk])
    return editor, url, ".field-uploaded_by_name .readonly", "autor_test"


def _submission_reviewed_by_another_editor(groups, editor, autor):
    other = _account("editora_dos", groups["editor"])
    submission = Submission.objects.create(
        author_name="Ana",
        author_email="ana@example.com",
        type="poesia",
        title="Umbral",
        body="Versos",
        reviewer=other,
    )
    url = reverse("admin:submissions_submission_change", args=[submission.pk])
    return editor, url, ".field-reviewer_name .readonly", "editora_dos"


def _own_text_for_its_author(groups, editor, autor):
    article = make_article(owner=autor)
    url = reverse("admin:content_article_change", args=[article.pk])
    return autor, url, ".field-owner_name .readonly", "autor_test"


def _contributor_for_an_author(groups, editor, autor):
    account = get_user_model().objects.create_user("lucia", password="pw")
    contributor = Contributor.objects.create(
        slug="lucia-prado", display_name="Lucía Prado", user=account
    )
    url = reverse("admin:people_contributor_change", args=[contributor.pk])
    return autor, url, ".field-user_name .readonly", "lucia"


@pytest.mark.parametrize(
    "case",
    [
        _note_by_another_editor,
        _image_uploaded_by_an_author,
        _submission_reviewed_by_another_editor,
        _own_text_for_its_author,
        _contributor_for_an_author,
    ],
)
def test_an_account_is_read_by_its_name(client, groups, editor, autor, case):
    viewer, url, selector, name = case(groups, editor, autor)
    client.force_login(viewer)
    page = soup(client, url)
    assert _texts(page.select(selector)) == [name]
    assert not page.select('a[href*="/admin/auth/user/"]')


def _read_only_names(model_admin, request):
    """Los campos que la ficha enseña sin dejar cambiarlos: los de solo lectura y, a quien solo
    puede leerla, todos."""
    if model_admin.has_view_permission(request) and not model_admin.has_change_permission(request):
        return flatten_fieldsets(model_admin.get_fieldsets(request))
    return model_admin.get_readonly_fields(request)


def test_no_read_only_field_links_to_an_account(editor, autor):
    """Django enlaza un campo de solo lectura a la ficha de lo que nombra: si nombra una cuenta,
    a una ficha que ni el editor ni la autora pueden abrir."""
    User = get_user_model()
    seen, linked = set(), []
    for user in (editor, autor):
        request = _request(user)
        for model_admin in admin.site._registry.values():
            if not model_admin.has_module_permission(request):
                continue
            for each in [model_admin, *model_admin.get_inline_instances(request)]:
                for name in _read_only_names(each, request):
                    seen.add(name)
                    field = next((f for f in each.model._meta.get_fields() if f.name == name), None)
                    if field is not None and field.is_relation and field.related_model is User:
                        linked.append(f"{user}: {each.model._meta.label}.{name}")
    # Control: llega a las cuentas que se leen por su nombre.
    assert {"author_name", "uploaded_by_name", "reviewer_name", "owner_name", "user_name"} <= seen
    assert not linked, "cuentas enlazadas: " + ", ".join(sorted(linked))
