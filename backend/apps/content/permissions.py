"""Autorización a nivel de objeto y estado para el flujo editorial."""

from .models import EditorialStatus

# El autor solo puede editar su pieza (artículo o poema) en estos estados.
EDITABLE_BY_OWNER = {EditorialStatus.DRAFT, EditorialStatus.CHANGES_REQUESTED}


def is_editor(user):
    """Editor o superior (grupos editor/admin, o superusuario)."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=["admin", "editor"]).exists()
    )


def is_owner(user, item):
    return user.is_authenticated and item.owner_id == user.id


def can_edit_item(user, item):
    """El permiso depende del rol Y del estado de la pieza editorial."""
    if not user.is_authenticated:
        return False
    if is_editor(user):
        return True
    return is_owner(user, item) and item.status in EDITABLE_BY_OWNER
