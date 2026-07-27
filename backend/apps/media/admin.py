from django.contrib import admin

from .models import MediaAsset, Recording


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "width", "height", "created_at"]
    search_fields = ["alt_text", "caption", "credit"]
    readonly_fields = ["width", "height", "created_at"]


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "featured", "published", "recorded_on"]
    list_filter = ["kind", "featured", "published"]
    search_fields = ["title", "description"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["poster"]
    filter_horizontal = ["participants"]
    readonly_fields = ["created_at"]
