from django.apps import AppConfig


class ContentConfig(AppConfig):
    """Artículos, poemas, colecciones y páginas: el flujo editorial."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    verbose_name = "Contenido"
