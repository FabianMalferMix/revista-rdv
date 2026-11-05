"""Lo que comparten los modelos de varias apps."""

from django.db import models


class TimestampedModel(models.Model):
    """Cuándo se creó la fila y cuándo se guardó por última vez. `updated_at` es la fecha que los
    sitemaps anuncian (`lastmod`). Un `update()` sobre una consulta no la cambia, y un
    `save(update_fields=…)` solo si la nombra."""

    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        abstract = True
