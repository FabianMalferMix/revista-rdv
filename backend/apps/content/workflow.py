"""Máquina de estados editorial (versión colapsada: 8 estados, sin corrector).

Compartida por todas las piezas que heredan de EditorialItem (artículos y poemas).
Las transiciones se validan aquí en el servidor, nunca en la UI. Cada movimiento
deja un rastro inmutable en EditorialTransition (enlace genérico a la pieza).
"""

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import EditorialStatus, EditorialTransition
from .permissions import is_editor, is_owner

S = EditorialStatus

# nombre -> (estados_origen, estado_destino, roles_permitidos)
#   "editor" = editor o admin ; "owner" = dueño de la pieza
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


def _allowed(user, item, roles):
    if "editor" in roles and is_editor(user):
        return True
    if "owner" in roles and is_owner(user, item):
        return True
    return False


def available_transitions(user, item):
    """Transiciones que este usuario puede disparar sobre esta pieza ahora."""
    return [
        name
        for name, (froms, _to, roles) in TRANSITIONS.items()
        if item.status in froms and _allowed(user, item, roles)
    ]


def perform_transition(item, name, user, note=""):
    if name not in TRANSITIONS:
        raise ValueError(f"Transición desconocida: {name!r}")

    froms, to_state, roles = TRANSITIONS[name]
    if item.status not in froms:
        raise ValueError(f"No se puede '{name}' desde el estado '{item.status}'.")
    if not _allowed(user, item, roles):
        raise PermissionDenied(f"Sin permiso para '{name}'.")

    from_status = item.status
    item.status = to_state
    if to_state == S.PUBLISHED and item.published_at is None:
        item.published_at = timezone.now()
    item.save(update_fields=["status", "published_at", "updated_at"])

    EditorialTransition.objects.create(
        item=item,
        from_status=from_status,
        to_status=to_state,
        actor=user if getattr(user, "is_authenticated", False) else None,
        note=note,
    )
    return item
