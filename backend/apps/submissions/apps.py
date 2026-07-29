from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.submissions"
    verbose_name = "Envíos"

    def ready(self):
        from apps.media.filecleanup import register

        from .models import Submission

        # El adjunto es un manuscrito en almacenamiento privado: al borrar el envío debe
        # desaparecer del disco, o una petición de supresión no se cumple de verdad (S-13).
        register(Submission, "file")
