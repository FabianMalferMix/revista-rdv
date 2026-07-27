from django.contrib import admin

from .models import SiteProfile, SiteSocialLink


class SiteSocialLinkInline(admin.TabularInline):
    model = SiteSocialLink
    extra = 1


@admin.register(SiteProfile)
class SiteProfileAdmin(admin.ModelAdmin):
    inlines = [SiteSocialLinkInline]
    autocomplete_fields = ["featured_recording"]

    def has_add_permission(self, request):
        # Singleton: solo se puede crear si aún no existe.
        return not SiteProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
