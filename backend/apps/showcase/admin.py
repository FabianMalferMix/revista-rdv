from django.contrib import admin

from .models import (
    Partner,
    PressMention,
    Publication,
    SiteProfile,
    SiteSocialLink,
    WhereToBuy,
)


class SiteSocialLinkInline(admin.TabularInline):
    model = SiteSocialLink
    extra = 1


@admin.register(SiteProfile)
class SiteProfileAdmin(admin.ModelAdmin):
    inlines = [SiteSocialLinkInline]
    autocomplete_fields = [
        "featured_recording",
        "featured_poem",
        "og_image",
        "hero_image",
        "hero_image_phone",
    ]

    def has_add_permission(self, request):
        # Fila única: solo se crea si aún no existe, y con el permiso de crearla.
        return super().has_add_permission(request) and not SiteProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class WhereToBuyInline(admin.TabularInline):
    model = WhereToBuy
    extra = 1


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "year", "is_own", "published", "featured"]
    list_filter = ["published", "featured", "kind", "is_own"]
    search_fields = ["title", "synopsis", "isbn"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["publisher", "cover"]
    filter_horizontal = ["participants"]
    inlines = [WhereToBuyInline]


@admin.register(PressMention)
class PressMentionAdmin(admin.ModelAdmin):
    list_display = ["outlet", "title", "kind", "published_on", "published"]
    list_filter = ["published", "kind"]
    search_fields = ["title", "outlet", "author", "quote"]
    autocomplete_fields = ["logo"]


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "active"]
    list_filter = ["active", "kind"]
    search_fields = ["name", "description"]
    autocomplete_fields = ["logo"]
