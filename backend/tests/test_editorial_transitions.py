"""La tabla de `workflow.TRANSITIONS`, ejecutada desde el panel por HTTP con los grupos reales.

Cada transición mueve una pieza de cada uno de sus orígenes a su destino y deja su entrada en la
bitácora; desde cualquier otro estado no hace nada. Y el rol al que la tabla no se la da no la
ejecuta: en las de editor, la autora dueña de la pieza; en «enviar a revisión», otra autora.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.content.workflow import TRANSITIONS

pytestmark = pytest.mark.django_db

MODELS = ["article", "poem"]


@pytest.fixture
def make_piece(make_article, make_poem):
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
    sources, target, _roles = TRANSITIONS[transition]
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
    sources, target, roles = TRANSITIONS[transition]
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
