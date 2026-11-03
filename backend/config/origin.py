"""El origen fijo de las URL absolutas: SITE_URL.

Canonical, og:url, imágenes para compartir, JSON-LD, robots, sitemap y feeds salen de aquí y
no del Host de cada petición. El sitio responde en un solo dominio, y un Host distinto (www,
una IP, un proxy mal configurado) no puede cambiar la identidad de una página ni los enlaces
de un feed.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap


def site_origin():
    """«https://dominio», sin barra final."""
    return settings.SITE_URL


def site_host():
    """El dominio (con el puerto, si lo hay), como se imprime en el dossier."""
    return urlsplit(settings.SITE_URL).netloc


def absolute_url(path):
    """La URL absoluta de una ruta del sitio o de un archivo de MEDIA_URL."""
    if path.startswith(("http://", "https://")):
        return path
    return f"{site_origin()}/{path.lstrip('/')}"


class FixedOriginSitemap(Sitemap):
    """Sitemap con el esquema y el dominio de SITE_URL, no los de la petición."""

    def get_protocol(self, protocol=None):
        return urlsplit(settings.SITE_URL).scheme

    def get_domain(self, site=None):
        return site_host()
