from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Call, Submission


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ["title", "opens_at", "closes_at", "open_now"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}

    @admin.display(boolean=True, description="Abierta")
    def open_now(self, obj):
        return obj.is_open


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["title", "author_name", "status", "call", "created_at"]
    list_filter = ["status", "call"]
    search_fields = ["title", "author_name", "author_email"]
    autocomplete_fields = ["reviewer", "call"]
    exclude = ["file"]  # el adjunto se descarga por la vista protegida, no se sirve
    readonly_fields = ["created_at", "archivo"]

    @admin.display(description="Archivo adjunto")
    def archivo(self, obj):
        if obj.pk and obj.file:
            url = reverse("submissions:file", args=[obj.pk])
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">Descargar adjunto</a>', url
            )
        return "—"
