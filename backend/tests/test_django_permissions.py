"""El flujo editorial y los envíos deciden con los permisos de Django, no con el nombre del grupo.

Retirar un permiso al grupo editor le quita lo que ese permiso abre: la acción desaparece del
panel, su POST no mueve la pieza y `perform_transition` la rechaza por cualquier otro camino;
la descarga de un adjunto responde 404.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.content import workflow
from apps.content.models import EditorialStatus
from apps.people import roles
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db
S = EditorialStatus
User = get_user_model()


def _permission(dotted):
    app_label, codename = dotted.split(".")
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def _offers(client, url, action):
    return f'value="{action}"' in client.get(url).content.decode()


@pytest.mark.parametrize(
    ("dotted", "model", "status", "transition"),
    [
        ("content.publish_article", "article", S.APPROVED, "publish"),
        ("content.review_article", "article", S.IN_REVIEW, "accept"),
        ("content.publish_poem", "poem", S.APPROVED, "publish"),
        ("content.review_poem", "poem", S.IN_REVIEW, "accept"),
    ],
)
def test_withdrawing_a_permission_takes_its_action_away(
    client, groups, editor, make_article, make_poem, dotted, model, status, transition
):
    piece = (make_article if model == "article" else make_poem)(status=status)
    url = reverse(f"admin:content_{model}_changelist")
    client.force_login(editor)
    assert _offers(client, url, f"do_{transition}"), "control: con el permiso, la acción está"
    groups[roles.EDITOR].permissions.remove(_permission(dotted))
    assert not _offers(client, url, f"do_{transition}")
    client.post(url, {"action": f"do_{transition}", "_selected_action": [piece.pk]})
    piece.refresh_from_db()
    assert piece.status == status
    with pytest.raises(PermissionDenied):
        workflow.perform_transition(piece, transition, User.objects.get(pk=editor.pk))


def test_withdrawing_view_submission_hides_the_attachments(client, groups, editor):
    submission = Submission.objects.create(
        author_name="A",
        author_email="a@a.com",
        type="reseña",
        title="Privado",
        body="cuerpo",
        file=SimpleUploadedFile("m.txt", b"contenido-secreto"),
    )
    url = reverse("submissions:file", args=[submission.pk])
    client.force_login(editor)
    response = client.get(url)
    assert response.status_code == 200, "control: con el permiso, la descarga sale"
    assert b"".join(response.streaming_content) == b"contenido-secreto"
    groups[roles.EDITOR].permissions.remove(_permission("submissions.view_submission"))
    assert client.get(url).status_code == 404
