from django.apps import AppConfig
from django.db.models import Q
from django.db.models.signals import post_save


class ShowcaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.showcase"
    verbose_name = "Colectivo"

    def ready(self):
        # Dentro de ready() y no arriba: estos módulos importan modelos, y apps.py se importa
        # antes de que estén cargados.
        from apps.media.services import register_portada_use

        from .models import SiteProfile
        from .signals import process_portada_images

        # La biblioteca de imágenes hace las copias de portada de las imágenes que el perfil
        # elige como obra; no sabe qué es una portada.
        register_portada_use(
            lambda asset: SiteProfile.objects.filter(
                Q(hero_image=asset) | Q(hero_image_phone=asset)
            ).exists()
        )
        post_save.connect(
            process_portada_images,
            sender=SiteProfile,
            dispatch_uid="showcase.process_portada_images",
        )
