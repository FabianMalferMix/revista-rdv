"""La tabla de `workflow.TRANSITIONS`, ejecutada desde el panel por HTTP con los grupos reales.

Cada transición mueve una pieza de cada uno de sus orígenes a su destino y deja su entrada en la
bitácora; desde cualquier otro estado no hace nada. Y el rol al que la tabla no se la da no la
ejecuta: en las de editor, la autora dueña de la pieza; en «enviar a revisión», otra autora.
Los avisos de cada acción nombran la acción y los estados como el panel.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.content.workflow import TRANSITIONS
from tests.factories import make_article, make_poem, soup

pytestmark = pytest.mark.django_db

MODELS = ["article", "poem"]


@pytest.fixture
def make_piece():
    def _make(model, owner, status, transition):
        make = make_article if model == "article" else make_poem
        # Sin fecha propia: la de la fábrica, si su estado la pide.
        return make(owner=owner, status=status)

    return _make


def _run_action(client, user, model, transition, *pieces):
    client.force_login(user)
    data = {"action": f"do_{transition}", "_selected_action": [piece.pk for piece in pieces]}
    if transition == "schedule":
        # «Programar» pide la fecha en su página intermedia: se confirma con una futura.
        tomorrow = timezone.localtime() + timedelta(days=1)
        data.update(apply="1", published_at=tomorrow.strftime("%Y-%m-%dT%H:%M"))
    return client.post(reverse(f"admin:content_{model}_changelist"), data)


def _log(piece):
    return list(piece.transitions.values_list("from_status", "to_status", "actor"))


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("transition", TRANSITIONS)
def test_the_editor_moves_pieces_only_along_the_table(
    client, editor, autor, make_piece, model, transition
):
    """Una pieza en cada estado, todas en la misma acción del panel."""
    sources, target, _roles, _label = TRANSITIONS[transition]
    pieces = {
        status: make_piece(model, autor, status, transition) for status in EditorialStatus.values
    }
    response = _run_action(client, editor, model, transition, *pieces.values())
    assert response.status_code == 302
    for status, piece in pieces.items():
        piece.refresh_from_db()
        if status in sources:
            assert (piece.status, _log(piece)) == (target, [(status, target, editor.pk)]), status
        else:
            assert (piece.status, _log(piece)) == (status, []), status


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("transition", TRANSITIONS)
def test_the_role_the_table_leaves_out_cannot_run_it(
    client, groups, editor, autor, make_piece, model, transition
):
    sources, target, roles, _label = TRANSITIONS[transition]
    origin = sorted(sources)[0]
    piece = make_piece(model, autor, origin, transition)
    if "owner" in roles:
        denied = get_user_model().objects.create_user("otra_autora", password="pw", is_staff=True)
        denied.groups.add(groups["autor"])
        allowed = autor
    else:
        denied, allowed = autor, editor
    _run_action(client, denied, model, transition, piece)
    piece.refresh_from_db()
    assert (piece.status, _log(piece)) == (origin, [])
    # Control: con el rol que la tabla sí nombra, la misma acción mueve la pieza.
    _run_action(client, allowed, model, transition, piece)
    piece.refresh_from_db()
    assert (piece.status, _log(piece)) == (target, [(origin, target, allowed.pk)])


def _messages(client, model):
    """Los avisos que enseña la lista a la que vuelve el panel tras la acción."""
    page = soup(client, reverse(f"admin:content_{model}_changelist"))
    return [" ".join(item.get_text().split()) for item in page.select("ul.messagelist li")]


def test_the_panel_says_what_moved_and_what_could_not(client, editor, autor):
    approved = make_article(owner=autor, status=EditorialStatus.APPROVED)
    in_review = make_article(
        owner=autor, status=EditorialStatus.IN_REVIEW, title="Correspondencias"
    )
    _run_action(client, editor, "article", "publish", approved, in_review)
    assert _messages(client, "article") == [
        "Correspondencias: no se puede publicar desde el estado «En revisión».",
        "1 artículo pasó a «Publicado».",
    ]


def test_the_count_of_moved_pieces_agrees_in_number(client, editor, autor):
    poems = [make_poem(owner=autor, status=EditorialStatus.APPROVED) for _ in range(2)]
    _run_action(client, editor, "poem", "publish", *poems)
    assert _messages(client, "poem") == ["2 poemas pasaron a «Publicado»."]


def test_without_the_permission_the_warning_names_the_action(client, groups, editor, autor):
    """Sin el permiso de revisar, el editor sigue viendo «Enviar a revisión», que la dueña pide
    con el de cambiar: la pieza ajena no se mueve, y el aviso dice por qué."""
    groups["editor"].permissions.remove(
        Permission.objects.get(content_type__app_label="content", codename="review_article")
    )
    draft = make_article(owner=autor, title="Correspondencias")
    _run_action(client, editor, "article", "submit", draft)
    assert _messages(client, "article") == ["Correspondencias: sin permiso para enviar a revisión."]
    draft.refresh_from_db()
    assert draft.status == EditorialStatus.DRAFT


def test_each_action_is_named_like_its_warnings(client, editor):
    """Los avisos nombran cada acción con las palabras de su opción en el desplegable."""
    make_article(owner=editor)
    client.force_login(editor)
    page = soup(client, reverse("admin:content_article_changelist"))
    options = {
        option["value"]: option.get_text().lower()
        for option in page.select("select[name=action] option")
    }
    # Control: el desplegable ofrece todas las acciones del flujo.
    assert {f"do_{name}" for name in TRANSITIONS} <= set(options), options
    unnamed = sorted(
        f"{name}: «{transition.label}» no está en «{options[f'do_{name}']}»"
        for name, transition in TRANSITIONS.items()
        if transition.label not in options[f"do_{name}"]
    )
    assert not unnamed, "; ".join(unnamed)
