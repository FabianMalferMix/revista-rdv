"""Los `<link>` de las hojas del sitio, una por capa, en el orden de la cascada.

La lista es `STYLESHEETS` (config/staticfiles.py). La etiqueta no lee el contexto, así que sirve
también en la página del error 500, que se pinta sin procesadores de contexto, y allí va sin
versión. Las demás páginas le pasan `version_estaticos`, el sufijo que rompe la caché en
desarrollo (config/context_processors.py), y cada URL lo lleva.
"""

from django import template
from django.templatetags.static import static
from django.utils.html import format_html_join

from config.staticfiles import STYLESHEETS

register = template.Library()


@register.simple_tag
def stylesheet_links(version=""):
    """Un `<link rel="stylesheet">` por hoja, en el orden de la lista, con `version` tras la URL."""
    return format_html_join(
        "\n  ",
        '<link rel="stylesheet" href="{}{}">',
        ((static(path), version) for path in STYLESHEETS),
    )
