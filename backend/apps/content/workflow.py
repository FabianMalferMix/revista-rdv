"""Máquina de estados editorial (versión colapsada: 8 estados, sin corrector).

Compartida por todas las piezas que heredan de EditorialItem (artículos y poemas).
Las transiciones se validan aquí en el servidor, nunca en la UI. Cada movimiento
deja un rastro inmutable en EditorialTransition (enlace genérico a la pieza).
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import EditorialStatus, EditorialTransition
from .permissions import is_owner

S = EditorialStatus

# Quién puede cada transición: la dueña de la pieza, o quien tenga el permiso de Django de
# revisar o de publicar ese tipo de pieza (`review_article`, `publish_poem`…). Los reparte
# la matriz de roles (apps/people/roles.py); el panel los pide en cada acción.
OWNER = "owner"
REVIEW = "review"
PUBLISH = "publish"

# nombre -> (estados_origen, estado_destino, quién)
TRANSITIONS = {
    "submit": ({S.DRAFT, S.CHANGES_REQUESTED}, S.IN_REVIEW, (OWNER, REVIEW)),
    "request_changes": ({S.IN_REVIEW}, S.CHANGES_REQUESTED, (REVIEW,)),
    "accept": ({S.IN_REVIEW}, S.APPROVED, (REVIEW,)),
    "reject": ({S.IN_REVIEW}, S.REJECTED, (REVIEW,)),
    "schedule": ({S.APPROVED}, S.SCHEDULED, (PUBLISH,)),
    "publish": ({S.APPROVED, S.SCHEDULED}, S.PUBLISHED, (PUBLISH,)),
    "unpublish": ({S.PUBLISHED}, S.DRAFT, (PUBLISH,)),
    "archive": ({S.PUBLISHED}, S.ARCHIVED, (PUBLISH,)),
    "restore": ({S.ARCHIVED}, S.PUBLISHED, (PUBLISH,)),
}


def permission_for(piece, action):
    """El permiso de Django de una acción del flujo sobre un tipo de pieza (modelo o instancia)."""
    return f"{piece._meta.app_label}.{action}_{piece._meta.model_name}"


def _allowed(user, item, who):
    if OWNER in who and is_owner(user, item):
        return True
    return any(user.has_perm(permission_for(item, action)) for action in who if action != OWNER)


def available_transitions(user, item):
    """Transiciones que este usuario puede disparar sobre esta pieza ahora."""
    return [
        name
        for name, (froms, _to, who) in TRANSITIONS.items()
        if item.status in froms and _allowed(user, item, who)
    ]


def perform_transition(item, name, user, note=""):
    if name not in TRANSITIONS:
        raise ValueError(f"Transición desconocida: {name!r}")

    froms, to_state, who = TRANSITIONS[name]
    # Chequeos rápidos (mensajes claros para el caso común, con el estado en memoria).
    if item.status not in froms:
        raise ValueError(f"No se puede '{name}' desde el estado '{item.status}'.")
    if not _allowed(user, item, who):
        raise PermissionDenied(f"Sin permiso para '{name}'.")

    with transaction.atomic():
        # Re-lee la pieza bajo lock de fila y revalida el estado de forma autoritativa:
        # cierra la ventana de carrera entre editores o con la publicación programada.
        locked = type(item).objects.select_for_update().get(pk=item.pk)
        if locked.status not in froms:
            raise ValueError(f"No se puede '{name}' desde el estado '{locked.status}'.")

        # Programar exige fecha futura: sin ella la pieza quedaría SCHEDULED para
        # siempre (publish_due_items filtra published_at__lte=now, y NULL nunca lo cumple).
        if name == "schedule" and (
            locked.published_at is None or locked.published_at <= timezone.now()
        ):
            raise ValueError("Programar requiere una fecha de publicación futura.")

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
