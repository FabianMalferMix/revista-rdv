from django.apps import AppConfig


class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.media"
    verbose_name = "Medios"

    def ready(self):
        from PIL import Image

        from .filecleanup import register
        from .models import MediaAsset, Recording
        from .validators import MAX_IMAGE_PIXELS

        # Nada mayor se decodifica: una imagen enorme agotaría la memoria del proceso.
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

        # Los archivos se borran del almacenamiento al borrar o reemplazar la fila
        # (hallazgo S-13). MediaAsset arrastra además sus derivados de srcset.
        register(MediaAsset, "file")
        register(Recording, "file")
