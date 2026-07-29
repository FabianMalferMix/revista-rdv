from django.apps import AppConfig


class ShowcaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.showcase"
    verbose_name = "Colectivo"

    def ready(self):
        from apps.media.filecleanup import register

        from .models import Publication, SiteProfile

        # Los PDF se borran del disco al borrar o reemplazar la fila (hallazgo S-13).
        register(Publication, "pdf")
        register(SiteProfile, "dossier_pdf")
