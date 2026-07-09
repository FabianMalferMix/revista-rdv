"""Autorización a nivel de objeto y estado para el flujo editorial."""
from .models import ArticleStatus

# El autor solo puede editar su artículo en estos estados.
EDITABLE_BY_OWNER = {ArticleStatus.DRAFT, ArticleStatus.CHANGES_REQUESTED}


def is_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="admin").exists()
    )


def is_editor(user):
    """Editor o superior (grupos editor/admin, o superusuario)."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=["admin", "editor"]).exists()
    )


def is_owner(user, article):
    return user.is_authenticated and article.owner_id == user.id


def can_edit_article(user, article):
    """El permiso depende del rol Y del estado del artículo."""
    if not user.is_authenticated:
        return False
    if is_editor(user):
        return True
    return is_owner(user, article) and article.status in EDITABLE_BY_OWNER


def can_moderate_comments(user):
    # Solo editor y superiores; el autor no modera su propio hilo.
    return is_editor(user)
