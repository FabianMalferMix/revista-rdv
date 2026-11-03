from django.contrib import admin, messages
from django.db.models import Count, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce

from config.publishing import FrozenSlugAdminMixin

from .models import MediaAsset, Recording


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "used_in", "width", "height", "uploaded_by", "created_at"]
    search_fields = ["alt_text", "caption", "credit"]
    # `uploaded_by` era un <select> editable con TODAS las cuentas del sistema: el rol
    # más bajo (autor) las enumeraba —nombres de usuario del equipo— y además podía
    # atribuir una subida a otra persona. Ahora es automático y no falsificable.
    readonly_fields = ["width", "height", "uploaded_by", "created_at"]

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        # Cuántas veces la usa cada relación, en la misma consulta del listado.
        queryset = super().get_queryset(request)
        for alias, model, field in _uses():
            count = (
                model._base_manager.filter(**{field: OuterRef("pk")})
                .order_by()
                .values(field)
                .annotate(n=Count("pk"))
                .values("n")
            )
            queryset = queryset.annotate(
                **{alias: Coalesce(Subquery(count, output_field=IntegerField()), 0)}
            )
        return queryset

    @admin.display(description="Usado en")
    def used_in(self, obj):
        uses = {}
        for alias, model, _ in _uses():
            if getattr(obj, alias, 0):
                name = model._meta.verbose_name
                uses[name] = uses.get(name, 0) + getattr(obj, alias)
        return ", ".join(f"{name} ({n})" if n > 1 else name for name, n in uses.items()) or "—"


def _uses():
    """Las relaciones que usan una imagen, como (alias, modelo, campo): retratos, tapas, afiches,
    fotos de un evento, la obra de la portada… Mientras alguna la use, no se puede borrar."""
    relations = [
        field
        for field in MediaAsset._meta.get_fields(include_hidden=True)
        if field.is_relation and field.auto_created and not field.concrete
    ]
    return [(f"uses_{i}", rel.related_model, rel.field.name) for i, rel in enumerate(relations)]


@admin.register(Recording)
class RecordingAdmin(FrozenSlugAdminMixin, admin.ModelAdmin):
    list_display = ["title", "kind", "featured", "published", "recorded_on"]
    list_filter = ["kind", "featured", "published"]
    search_fields = ["title", "description"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["poster"]
    filter_horizontal = ["participants"]
    readonly_fields = ["created_at"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Un aviso, no un bloqueo: el colectivo puede publicar y escribir la transcripción después.
        if obj.published and obj.kind == Recording.Kind.AUDIO and not obj.transcript:
            from apps.content.models import Poem

            if not Poem.objects.filter(recording=obj).exists():
                messages.warning(
                    request,
                    f"“{obj.title}” está publicado sin transcripción ni poema enlazado: quien no "
                    "puede escucharlo no tiene qué leer. Escribe la transcripción o enlaza el "
                    "registro desde la ficha del poema.",
                )
