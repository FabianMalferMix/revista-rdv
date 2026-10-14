"""Consultas de contenido que usan varias apps (la portada, el dossier)."""

from apps.media.models import Recording

from .models import Article, EditorialStatus, Poem


def ultima_publicacion():
    """Cuándo publicó el colectivo por última vez: un poema, un texto o un registro. Es el
    «Actualizado el…» del cierre de la portada y de la ficha del dossier, en una sola consulta.
    Cuenta la fecha de publicación y no la de edición: corregir una errata no hace más reciente
    la portada."""
    fechas = (
        Article.objects.filter(status=EditorialStatus.PUBLISHED, published_at__isnull=False)
        .order_by()
        .values_list("published_at", flat=True)
        .union(
            Poem.objects.filter(status=EditorialStatus.PUBLISHED, published_at__isnull=False)
            .order_by()
            .values_list("published_at", flat=True),
            Recording.objects.filter(published=True, published_at__isnull=False)
            .order_by()
            .values_list("published_at", flat=True),
        )
        .order_by("-published_at")
    )
    return next(iter(fechas[:1]), None)
