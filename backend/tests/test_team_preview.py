"""La vista previa del equipo: la ficha de algo sin publicar se sirve a quien puede verlo en el panel.

Con la franja «Vista previa: no publicado», sin indexar y sin guardarse en cachés compartidas. Un
anónimo recibe 404, como siempre, y una autora no ve los borradores ajenos. Lo publicado se sirve
igual que antes, sin franja.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.content.models import Collection, EditorialStatus, Page, PublishStatus
from apps.people import roles
from tests.factories import make_event, make_publication, make_recording

pytestmark = pytest.mark.django_db
S = EditorialStatus
BANNER = "Vista previa: no publicado"


def _is_preview(response):
    content = response.content.decode()
    return (
        response.status_code == 200
        and BANNER in content
        and '<meta name="robots" content="noindex' in content
        and response.get("X-Robots-Tag") == "noindex"
        and "no-store" in response.get("Cache-Control", "")
    )


@pytest.fixture
def other_author(groups):
    user = get_user_model().objects.create_user("otra_autora", password="pw", is_staff=True)
    user.groups.add(groups[roles.AUTHOR])
    return user


@pytest.mark.parametrize("model", ["article", "poem"])
def test_the_editor_and_the_owner_preview_a_draft_and_nobody_else(
    client, editor, autor, other_author, make_article, make_poem, model
):
    make = make_article if model == "article" else make_poem
    draft = make(owner=autor, status=S.IN_REVIEW)
    url = draft.get_absolute_url()
    assert client.get(url).status_code == 404
    for person in (editor, autor):
        client.force_login(person)
        assert _is_preview(client.get(url)), person
    client.force_login(other_author)
    assert client.get(url).status_code == 404
    # Control: lo publicado se ve igual que siempre, sin franja ni noindex.
    published = make(owner=autor, status=S.PUBLISHED)
    client.force_login(editor)
    response = client.get(published.get_absolute_url())
    assert response.status_code == 200
    assert BANNER not in response.content.decode()
    assert "X-Robots-Tag" not in response


def _unpublished():
    return {
        "registro": make_recording(slug="registro-oculto", published=False),
        "actividad": make_event(slug="actividad-oculta", published=False),
        "publicacion": make_publication(slug="publicacion-oculta", published=False),
        "coleccion": Collection.objects.create(
            slug="coleccion-oculta", title="Colección", status=PublishStatus.DRAFT
        ),
        "pagina": Page.objects.create(
            slug="pagina-oculta", title="Página", body="Texto", status=PublishStatus.DRAFT
        ),
    }


@pytest.mark.parametrize("kind", ["registro", "actividad", "publicacion", "coleccion", "pagina"])
def test_the_editor_previews_what_is_not_published_yet(client, editor, kind):
    url = _unpublished()[kind].get_absolute_url()
    assert client.get(url).status_code == 404
    client.force_login(editor)
    assert _is_preview(client.get(url))


def test_view_on_site_works_for_a_draft(client, editor, make_article):
    draft = make_article(status=S.DRAFT, published_at=None)
    client.force_login(editor)
    change = client.get(reverse("admin:content_article_change", args=[draft.pk]))
    assert "/admin/r/" in change.content.decode(), "control: el panel ofrece «Ver en el sitio»"
    content_type = ContentType.objects.get_for_model(draft).pk
    response = client.get(reverse("admin:view_on_site", args=[content_type, draft.pk]), follow=True)
    assert _is_preview(response)


def test_a_scheduled_piece_is_previewed_until_it_is_published(client, editor, make_article):
    scheduled = make_article(status=S.SCHEDULED, published_at=timezone.now() + timedelta(days=1))
    client.force_login(editor)
    assert _is_preview(client.get(scheduled.get_absolute_url()))


def test_without_access_to_the_panel_there_is_no_preview(client, groups, make_article):
    """Alguien que conserva los permisos de su grupo pero ya no entra al panel no ve borradores."""
    former = get_user_model().objects.create_user("ya-no-entra", password="pw", is_staff=False)
    former.groups.add(groups[roles.EDITOR])
    draft = make_article(status=S.DRAFT)
    client.force_login(former)
    assert client.get(draft.get_absolute_url()).status_code == 404
