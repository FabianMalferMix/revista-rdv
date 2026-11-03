"""«Publicado», definido en un solo lugar: lo que el sitio puede enseñar.

Hay dos familias. Lo que tiene un `status` se ve solo en «publicado»: los artículos y los poemas,
con su flujo editorial, y las colecciones y las páginas, con dos estados. Lo que tiene una casilla
se ve cuando está marcada: los registros, las actividades, las publicaciones y las menciones de
prensa, en `published`, y los aliados, en `active`.

Cada modelo monta su QuerySet como manager (`objects = ….as_manager()`), así que el filtro vale
también desde las relaciones (`member.events.published()`). Dentro de una consulta sobre otro
modelo se usa como subconsulta: `article__in=Article.objects.published()`. Fuera de estos
QuerySets el filtro no se escribe a mano, y tests/test_published_querysets.py lo vigila.

Las fichas piden su pieza con `piece_for`: a quien puede verla en el panel le sirven también lo
que no está publicado, como vista previa.
"""

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.db import models
from django.http import Http404

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


def piece_for(request, queryset, **lookup):
    """La pieza de una ficha pública: la publicada o, para quien puede verla en el panel, también
    la que no lo está (la vista previa del equipo). Devuelve (pieza, es_vista_previa), y 404 si
    no hay ninguna que esta persona pueda ver."""
    piece = queryset.published().filter(**lookup).first()
    if piece is not None:
        return piece, False
    piece = queryset.filter(**lookup).first()
    if piece is None or not can_preview(request, piece):
        raise Http404
    return piece, True


def can_preview(request, piece):
    """Quien es del equipo y ve esta pieza en el panel: con el permiso de verla y dentro de lo que
    el panel le enseña (una autora, solo lo suyo)."""
    user = request.user
    if not (user.is_active and user.is_staff):
        return False
    try:
        model_admin = admin.site.get_model_admin(type(piece))
    except NotRegistered:
        return False
    return (
        model_admin.has_view_permission(request, piece)
        and model_admin.get_queryset(request).filter(pk=piece.pk).exists()
    )


def marked_as_preview(response, preview):
    """La vista previa no se indexa ni se guarda en ninguna caché compartida."""
    if preview:
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex"
    return response


class FrozenSlugAdminMixin:
    """En el panel, la dirección (slug) de lo que ya es público es de solo lectura.

    Cambiarla dejaría en 404 los enlaces difundidos (prensa, dossiers, redes), porque las
    fichas no guardan direcciones anteriores. Lo que se publica con un estado o una casilla
    la congela al publicarse; lo demás (secciones, etiquetas, personas, obras), en cuanto
    existe, porque su ficha puede estar enlazada desde cualquier pieza publicada.
    """

    def slug_is_frozen(self, obj):
        if obj is None or obj.pk is None:
            return False
        queryset = type(obj)._default_manager.all()
        if isinstance(queryset, (EditorialQuerySet, PublishableQuerySet)):
            return queryset.published().filter(pk=obj.pk).exists()
        return True

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if self.slug_is_frozen(obj) and "slug" not in fields:
            fields.append("slug")
        return fields

    def get_prepopulated_fields(self, request, obj=None):
        # Un campo de solo lectura no está en el formulario: dejarlo en prepopulated_fields
        # rompería la ficha de cambio.
        if self.slug_is_frozen(obj):
            return {}
        return super().get_prepopulated_fields(request, obj)

    def get_fields(self, request, obj=None):
        # Sin `fields` ni `fieldsets`, Django pone los campos de solo lectura al final del
        # formulario. La dirección congelada conserva el sitio que tiene mientras se edita.
        fields = list(super().get_fields(request, obj))
        if not self.slug_is_frozen(obj) or "slug" not in fields:
            return fields
        editable_order = list(super().get_fields(request, None))
        if "slug" not in editable_order:
            return fields
        fields.remove("slug")
        position = editable_order.index("slug")
        previous = editable_order[position - 1] if position else None
        fields.insert(fields.index(previous) + 1 if previous in fields else 0, "slug")
        return fields
