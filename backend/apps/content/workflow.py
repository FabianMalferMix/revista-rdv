"""Máquina de estados editorial (versión colapsada: 8 estados, sin corrector).

Compartida por todas las piezas que heredan de EditorialItem (artículos y poemas).
Las transiciones se validan aquí en el servidor, nunca en la UI. Cada movimiento
deja un rastro inmutable en EditorialTransition (enlace genérico a la pieza).
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
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
    # Chequeos rápidos (mensajes claros para el caso común, con el estado en memoria).
    if item.status not in froms:
        raise ValueError(f"No se puede '{name}' desde el estado '{item.status}'.")
    if not _allowed(user, item, roles):
        raise PermissionDenied(f"Sin permiso para '{name}'.")

    with transaction.atomic():
        # Re-lee la pieza bajo lock de fila y revalida el estado de forma autoritativa:
        # cierra la ventana de carrera entre editores o con la publicación programada.
        locked = type(item).objects.select_for_update().get(pk=item.pk)
        if locked.status not in froms:
            raise ValueError(f"No se puede '{name}' desde el estado '{locked.status}'.")

        from_status = locked.status
        locked.status = to_state
        if to_state == S.PUBLISHED and locked.published_at is None:
            locked.published_at = timezone.now()
        locked.save(update_fields=["status", "published_at", "updated_at"])

        EditorialTransition.objects.create(
            item=locked,
            from_status=from_status,
            to_status=to_state,
            actor=user if getattr(user, "is_authenticated", False) else None,
            note=note,
        )

    # Refleja el nuevo estado en la instancia recibida (varios callers la reutilizan).
    item.refresh_from_db(fields=["status", "published_at", "updated_at"])
    return item
