from django.apps import AppConfig


class CommunityConfig(AppConfig):
    """Boletín de novedades para prensa y gestores."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.community"
    verbose_name = "Comunidad"
