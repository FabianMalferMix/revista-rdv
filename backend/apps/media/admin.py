from django.contrib import admin, messages

from config.publishing import FrozenSlugAdminMixin

from .models import MediaAsset, Recording


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "width", "height", "uploaded_by", "created_at"]
    search_fields = ["alt_text", "caption", "credit"]
    # `uploaded_by` era un <select> editable con TODAS las cuentas del sistema: el rol
    # más bajo (autor) las enumeraba —nombres de usuario del equipo— y además podía
    # atribuir una subida a otra persona. Ahora es automático y no falsificable.
    readonly_fields = ["width", "height", "uploaded_by", "created_at"]

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


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
                    f"«{obj.title}» está publicado sin transcripción ni poema enlazado: quien no "
                    "puede escucharlo no tiene qué leer. Escribe la transcripción o enlaza el "
                    "registro desde la ficha del poema.",
                )
