"""El nombre del sitio donde no hay procesadores de contexto: la página del error 500.

Las demás páginas firman con `site_name`, que da el procesador de contexto del perfil del sitio.
"""

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def fixed_site_name():
    """El nombre fijo del sitio (`SITE_NAME`), sin consultar la base."""
    return settings.SITE_NAME
