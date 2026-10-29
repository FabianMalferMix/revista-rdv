"""La matriz de roles (apps/people/roles.py), con los grupos reales y por el panel.

Cada modelo del proyecto está clasificado de forma explícita. Los grupos cumplen lo decidido: el
editor, todo salvo el perfil del sitio y las cuentas; la autora, sus textos y sus poemas, sin
editar el catálogo ni ver datos personales. Se comprueba con invariantes y por HTTP, no contra una
lista exacta. Y `setup_groups` sincroniza de forma aditiva.
"""

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.urls import reverse

from apps.content.models import Poem
from apps.people import roles
from apps.people.models import RoleGrant
from apps.reviews.models import Work

PROJECT_MODELS = {
    model._meta.label
    for model in apps.get_models()
    if model._meta.app_config.name.startswith("apps.")
}


def test_every_project_model_is_in_the_matrix():
    classified = set(roles.EDITOR_PERMISSIONS) | roles.ADMIN_ONLY
    assert PROJECT_MODELS - classified == set(), "modelos sin clasificar en roles.py"
    assert classified - PROJECT_MODELS == set(), "roles.py nombra modelos que no existen"
    assert set(roles.EDITOR_PERMISSIONS) & roles.ADMIN_ONLY == set()


def test_the_author_never_gets_more_than_the_editor():
    for label, actions in roles.AUTHOR_PERMISSIONS.items():
        assert actions <= roles.EDITOR_PERMISSIONS[label], label


def _codes(group):
    return {
        f"{perm.content_type.app_label}.{perm.codename}"
        for perm in group.permissions.select_related("content_type")
    }


@pytest.mark.django_db
def test_the_editor_manages_the_content_but_not_the_profile_nor_the_accounts(groups):
    codes = _codes(groups[roles.EDITOR])
    assert {
        "agenda.change_event",
        "showcase.change_publication",
        "showcase.change_partner",
        "content.change_poem",
        "submissions.view_submission",
    } <= codes
    assert {
        code for code in codes if code.startswith(("auth.", "showcase.")) and "site" in code
    } == set()
    assert not any(code.startswith("auth.") for code in codes)
    # La bitácora solo la escribe el flujo.
    assert "content.change_editorialtransition" not in codes


@pytest.mark.django_db
def test_the_author_writes_texts_and_poems_and_adds_works(groups):
    codes = _codes(groups[roles.AUTHOR])
    assert {
        "content.add_poem",
        "content.change_poem",
        "content.add_article",
        "reviews.add_work",
    } <= codes
    assert {"reviews.change_work", "content.delete_article", "content.delete_poem"} & codes == set()
    # Ni datos personales (envíos, suscriptores) ni lo que publica el colectivo por su cuenta.
    apps_seen = {code.split(".")[0] for code in codes}
    assert apps_seen & {"submissions", "community", "agenda", "showcase", "auth"} == set()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "status"),
    [
        ("admin:agenda_event_changelist", 200),
        ("admin:showcase_publication_changelist", 200),
        ("admin:content_poem_add", 200),
        ("admin:showcase_siteprofile_changelist", 403),
        ("admin:auth_user_changelist", 403),
    ],
)
def test_what_the_editor_opens_in_the_panel(client, editor, url_name, status):
    client.force_login(editor)
    assert client.get(reverse(url_name)).status_code == status


def _form_data(page, form_id):
    """Lo que enviaría el formulario del panel tal como se dibuja (con sus formularios de gestión)."""
    soup = BeautifulSoup(page.content, "html.parser")
    form = soup.select_one(f"form#{form_id}")
    data = {}
    for field in form.select("input[name], textarea[name], select[name]"):
        kind = field.get("type", "")
        if kind in {"submit", "checkbox", "file"} or field["name"].startswith("_"):
            continue
        if field.name == "select":
            chosen = field.select_one("option[selected]")
            data[field["name"]] = chosen["value"] if chosen else ""
        else:
            data[field["name"]] = field.text if field.name == "textarea" else field.get("value", "")
    return data


@pytest.mark.django_db
def test_the_author_creates_a_poem_from_the_panel(client, autor):
    client.force_login(autor)
    url = reverse("admin:content_poem_add")
    data = _form_data(client.get(url), "poem_form")
    data.update(
        {"title": "Un poema de la autora", "slug": "poema-de-la-autora", "body": "Un verso"}
    )
    response = client.post(url, data)
    if response.status_code != 302:
        context = response.context
        inlines = [inline.formset for inline in context["inline_admin_formsets"]]
        pytest.fail(
            f"{context['adminform'].form.errors} "
            f"{[(f.prefix, f.errors, f.non_form_errors()) for f in inlines]}"
        )
    poem = Poem.objects.get(slug="poema-de-la-autora")
    assert poem.owner == autor


@pytest.mark.django_db
def test_the_author_adds_works_but_does_not_edit_them(client, autor):
    client.force_login(autor)
    assert client.get(reverse("admin:reviews_work_add")).status_code == 200
    work = Work.objects.create(slug="obra-ajena", title="Obra ajena")
    url = reverse("admin:reviews_work_change", args=[work.pk])
    assert client.post(url, {"title": "Cambiada", "slug": "obra-ajena"}).status_code == 403
    work.refresh_from_db()
    assert work.title == "Obra ajena"


@pytest.mark.django_db
def test_the_first_sync_leaves_the_group_as_the_matrix_says():
    group = Group.objects.create(name=roles.AUTHOR)
    # Un grupo de antes de la matriz, con un permiso que ya no le corresponde.
    stray = Permission.objects.get(content_type__app_label="reviews", codename="change_work")
    group.permissions.add(stray)
    call_command("setup_groups", verbosity=0)
    assert set(group.permissions.all()) == set(roles.permissions_for(roles.AUTHOR))


@pytest.mark.django_db
def test_a_permission_new_in_the_matrix_reaches_an_existing_group(groups):
    editor = groups[roles.EDITOR]
    perm = Permission.objects.get(content_type__app_label="agenda", codename="add_event")
    # Como si la matriz lo hubiera ganado después de repartir lo demás.
    editor.permissions.remove(perm)
    RoleGrant.objects.filter(group=editor, permission=perm).delete()
    call_command("setup_groups", verbosity=0)
    assert editor.permissions.filter(pk=perm.pk).exists()
