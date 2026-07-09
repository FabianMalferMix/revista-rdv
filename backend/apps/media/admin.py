from django.contrib import admin

from .models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "width", "height", "created_at"]
    search_fields = ["alt_text", "caption", "credit"]
    readonly_fields = ["width", "height", "created_at"]
