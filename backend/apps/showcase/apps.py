from django.apps import AppConfig


class ShowcaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.showcase"
    verbose_name = "Colectivo"

    def ready(self):
        from django.db.models import Q
        from django.db.models.signals import post_save

        from apps.media.filecleanup import register
        from apps.media.models import MediaAsset

        from .models import Publication, SiteProfile

        # Los PDF se borran del disco al borrar o reemplazar la fila (hallazgo S-13).
        register(Publication, "pdf")
        register(SiteProfile, "dossier_pdf")

        def copias_de_la_portada(sender, instance, **kwargs):
            """Si se cambia el archivo de la imagen que ya es la portada, sus copias AVIF y
            WebP se rehacen con el archivo nuevo (las viejas las borra filecleanup). Vive
            aquí y no en media: la biblioteca de imágenes no sabe qué es una portada."""
            if SiteProfile.objects.filter(
                Q(hero_image=instance) | Q(hero_image_phone=instance)
            ).exists():
                instance.ensure_portada_derivatives()

        # weak=False: es una función local de ready(). Con la referencia débil de siempre
        # solo seguía viva por la caché de Django que la guarda con DEBUG; en producción
        # se perdía en silencio, como habría pasado con las de filecleanup.
        post_save.connect(
            copias_de_la_portada,
            sender=MediaAsset,
            weak=False,
            dispatch_uid="showcase.copias_de_la_portada",
        )
