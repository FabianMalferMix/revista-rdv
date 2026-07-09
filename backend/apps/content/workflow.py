"""Máquina de estados del artículo (versión colapsada: 8 estados, sin corrector).

Las transiciones se validan aquí en el servidor, nunca en la UI. Cada movimiento
deja un rastro inmutable en EditorialTransition.
"""

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import ArticleStatus, EditorialTransition
from .permissions import is_editor, is_owner

S = ArticleStatus

# nombre -> (estados_origen, estado_destino, roles_permitidos)
#   "editor" = editor o admin ; "owner" = dueño del artículo
TRANSITIONS = {
    "submit": ({S.DRAFT, S.CHANGES_REQUESTED}, S.IN_REVIEW, ("owner", "editor")),
    "request_changes": ({S.IN_REVIEW}, S.CHANGES_REQUESTED, ("editor",)),
    "accept": ({S.IN_REVIEW}, S.APPROVED, ("editor",)),
    "reject": ({S.IN_REVIEW}, S.REJECTED, ("editor",)),
    "schedule": ({S.APPROVED}, S.SCHEDULED, ("editor",)),
    "publish": ({S.APPROVED, S.SCHEDULED}, S.PUBLISHED, ("editor",)),
    "unpublish": ({S.PUBLISHED}, S.DRAFT, ("editor",)),
    "archive": ({S.PUBLISHED}, S.ARCHIVED, ("editor",)),
    "restore": ({S.ARCHIVED}, S.PUBLISHED, ("editor",)),
}


def _allowed(user, article, roles):
    if "editor" in roles and is_editor(user):
        return True
    if "owner" in roles and is_owner(user, article):
        return True
    return False


def available_transitions(user, article):
    """Transiciones que este usuario puede disparar sobre este artículo ahora."""
    return [
        name
        for name, (froms, _to, roles) in TRANSITIONS.items()
        if article.status in froms and _allowed(user, article, roles)
    ]


def perform_transition(article, name, user, note=""):
    if name not in TRANSITIONS:
        raise ValueError(f"Transición desconocida: {name!r}")

    froms, to_state, roles = TRANSITIONS[name]
    if article.status not in froms:
        raise ValueError(f"No se puede '{name}' desde el estado '{article.status}'.")
    if not _allowed(user, article, roles):
        raise PermissionDenied(f"Sin permiso para '{name}'.")

    from_status = article.status
    article.status = to_state
    if to_state == S.PUBLISHED and article.published_at is None:
        article.published_at = timezone.now()
    article.save(update_fields=["status", "published_at", "updated_at"])

    EditorialTransition.objects.create(
        article=article,
        from_status=from_status,
        to_status=to_state,
        actor=user if getattr(user, "is_authenticated", False) else None,
        note=note,
    )
    return article
