from django.core.checks import Error, register
from django.db import DatabaseError

from .models import LEGAL_PAGES, Page


@register(deploy=True)
def legal_pages_published(app_configs, **kwargs):
    """`check --deploy` falla si falta alguna página legal o no está publicada.

    Si la base no responde o no está migrada, también falla: sin comprobarlo, no se sabe
    si el pie y los formularios enlazan a una política que existe.
    """
    try:
        publicadas = set(
            Page.objects.published().filter(slug__in=LEGAL_PAGES).values_list("slug", flat=True)
        )
    except DatabaseError as error:
        return [
            Error(
                f"No se pudieron comprobar las páginas legales: {error}",
                hint="Migra la base antes de `check --deploy`.",
                id="content.E002",
            )
        ]
    return [
        Error(
            f"La página legal «{slug}» falta o no está publicada.",
            hint="El pie de todas las páginas y los formularios enlazan a ella.",
            id="content.E001",
        )
        for slug in LEGAL_PAGES
        if slug not in publicadas
    ]
