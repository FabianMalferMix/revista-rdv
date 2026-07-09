from django.contrib import admin

from .models import Contributor, SocialLink


class SocialLinkInline(admin.TabularInline):
    model = SocialLink
    extra = 1


@admin.register(Contributor)
class ContributorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user"]
    search_fields = ["display_name", "bio"]
    prepopulated_fields = {"slug": ("display_name",)}
    autocomplete_fields = ["user", "photo"]
    inlines = [SocialLinkInline]
