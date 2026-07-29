from django.contrib import admin

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
class RecordingAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "featured", "published", "recorded_on"]
    list_filter = ["kind", "featured", "published"]
    search_fields = ["title", "description"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["poster"]
    filter_horizontal = ["participants"]
    readonly_fields = ["created_at"]
