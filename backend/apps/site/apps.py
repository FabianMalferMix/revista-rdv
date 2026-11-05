from django.apps import AppConfig


class SiteConfig(AppConfig):
    """Lo que reúne a todas las apps: la portada, la búsqueda, el pie de las fichas, la
    navegación y los sitemaps. No tiene modelos: el perfil del sitio está en showcase."""

    name = "apps.site"
    label = "site"
    verbose_name = "Sitio"
