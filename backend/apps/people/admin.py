from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group, User

from config.panel import PanelWordingMixin, account_name
from config.publishing import FrozenSlugAdminMixin, ViewOnSiteIfVisibleMixin

from .models import Contributor, SocialLink

# Las cuentas y los grupos, con el panel de Django tal cual y sus selectores dobles (los grupos y
# los permisos) dichos como el resto del panel.
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(PanelWordingMixin, auth_admin.UserAdmin):
    pass


@admin.register(Group)
class GroupAdmin(PanelWordingMixin, auth_admin.GroupAdmin):
    pass


class SocialLinkInline(admin.TabularInline):
    model = SocialLink
    extra = 1


@admin.register(Contributor)
class ContributorAdmin(
    ViewOnSiteIfVisibleMixin, FrozenSlugAdminMixin, PanelWordingMixin, admin.ModelAdmin
):
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

    # Quien solo lee la ficha (la autora) lee la cuenta por su nombre: Django la enlazaría a la
    # ficha de la cuenta, que solo abre quien administra las cuentas.
    user_name = account_name(Contributor, "user")

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if self.has_change_permission(request, obj):
            return fieldsets
        return [
            (
                title,
                {
                    **options,
                    "fields": ["user_name" if f == "user" else f for f in options["fields"]],
                },
            )
            for title, options in fieldsets
        ]
