"""El HTML que escriben los autores (el cuerpo de los textos y de las páginas), saneado al mostrarlo.

El panel lo sanea al guardar, pero loaddata, las migraciones de datos y `update()` no pasan por
`save()`: la garantía está en la salida. tests/content/test_authored_html.py prohíbe `|safe`
en las plantillas, de modo que este filtro es el único camino del HTML de autor a la página.
"""

from functools import lru_cache

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

from apps.content.sanitize import clean_html

register = template.Library()


# La depuración depende también de SITE_URL (qué imágenes son del propio sitio): va en la clave.
@lru_cache(maxsize=256)
def _cleaned(html, site_url):
    return clean_html(html)


@register.filter
def authored_html(html):
    """El HTML de autor, depurado con la lista blanca de nh3. Cada proceso recuerda los 256
    cuerpos que pintó más recientemente, y esos no se vuelven a depurar."""
    # Se marca como seguro exactamente lo que devolvió `clean_html` con la lista blanca del sitio.
    cleaned = _cleaned(html or "", settings.SITE_URL)
    return mark_safe(cleaned)  # nosec B308, B703
