"""«Publicado», definido en un solo lugar: lo que el sitio puede enseñar.

Hay dos familias. Lo que tiene un `status` se ve solo en «publicado»: los artículos y los poemas,
con su flujo editorial, y las colecciones y las páginas, con dos estados. Lo que tiene una casilla
se ve cuando está marcada: los registros, las actividades, las publicaciones y las menciones de
prensa, en `published`, y los aliados, en `active`.

Cada modelo monta su QuerySet como manager (`objects = ….as_manager()`), así que el filtro vale
también desde las relaciones (`member.events.published()`). Dentro de una consulta sobre otro
modelo se usa como subconsulta: `article__in=Article.objects.published()`. Fuera de estos
QuerySets el filtro no se escribe a mano, y tests/test_published_querysets.py lo vigila.
"""

from django.db import models

# El valor de «publicado» de los dos enumerados de estado (EditorialStatus y PublishStatus).
PUBLISHED = "published"


class EditorialQuerySet(models.QuerySet):
    """Lo que se publica por su estado."""

    def published(self):
        return self.filter(status=PUBLISHED)


class PublishableQuerySet(models.QuerySet):
    """Lo que se publica con una casilla."""

    # El campo de la casilla: `published`, salvo en los aliados.
    published_field = "published"

    def published(self):
        return self.filter(**{self.published_field: True})
