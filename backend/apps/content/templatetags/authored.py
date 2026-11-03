"""El HTML que escriben los autores (el cuerpo de los textos y de las páginas), saneado al mostrarlo.

El panel lo sanea al guardar, pero loaddata, las migraciones de datos y `update()` no pasan por
`save()`: la garantía está en la salida. tests/test_authored_html.py prohíbe `|safe` en las
plantillas, de modo que este filtro es el único camino del HTML de autor a la página.
"""

from functools import lru_cache

from django import template
from django.utils.safestring import mark_safe

from apps.content.sanitize import clean_html

register = template.Library()


@lru_cache(maxsize=256)
def _cleaned(html):
    return clean_html(html)


@register.filter
def authored_html(html):
    """El HTML de autor, depurado con la lista blanca de nh3: cada cuerpo se depura una vez por
    proceso."""
    # Se marca como seguro exactamente lo que devolvió nh3 con la lista blanca del sitio.
    return mark_safe(_cleaned(html or ""))  # nosec B308, B703
