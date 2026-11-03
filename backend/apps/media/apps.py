from django.apps import AppConfig


class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.media"
    verbose_name = "Medios"

    def ready(self):
        from PIL import Image

        from .filecleanup import register_all
        from .validators import MAX_IMAGE_PIXELS

        # Nada mayor se decodifica: una imagen enorme agotaría la memoria del proceso.
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

        # Los archivos de todas las apps se borran del almacenamiento al borrar o reemplazar
        # la fila; MediaAsset arrastra además sus copias.
        register_all()
