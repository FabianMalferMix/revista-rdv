from django.apps import AppConfig


class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.media"
    verbose_name = "Medios"

    def ready(self):
        from .filecleanup import register
        from .models import MediaAsset, Recording

        # Los archivos se borran del almacenamiento al borrar o reemplazar la fila
        # (hallazgo S-13). MediaAsset arrastra además sus derivados de srcset.
        register(MediaAsset, "file")
        register(Recording, "file")
