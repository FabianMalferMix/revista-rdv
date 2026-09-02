from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    """Catálogo de obras, sus autores y editoriales."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"
    verbose_name = "Obras reseñadas"
