from django.contrib import admin

from .models import Contributor, SocialLink


class SocialLinkInline(admin.TabularInline):
    model = SocialLink
    extra = 1


@admin.register(Contributor)
class ContributorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "is_member", "active", "role", "member_since", "user"]
    list_filter = ["is_member", "active"]
    search_fields = ["display_name", "bio", "short_bio"]
    prepopulated_fields = {"slug": ("display_name",)}
    autocomplete_fields = ["user", "photo"]
    inlines = [SocialLinkInline]
    fieldsets = [
        (None, {"fields": ["display_name", "slug", "photo", "bio", "website", "user"]}),
        (
            "Integrante del colectivo",
            {
                "fields": [
                    "is_member",
                    "active",
                    "role",
                    "member_since",
                    "short_bio",
                    "poetics",
                    "position",
                ],
                "description": "Solo aplica si la persona integra el colectivo "
                "(perfil en /integrantes/).",
            },
        ),
    ]
