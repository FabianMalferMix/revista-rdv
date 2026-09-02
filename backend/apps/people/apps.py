from django.apps import AppConfig


class PeopleConfig(AppConfig):
    """Integrantes y colaboradores del colectivo."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.people"
    verbose_name = "Personas"
