"""La paginación de los listados: una sola manera de leer `?page=` y de responder cuando no vale.

Cada página de un listado es un recurso con su URL canónica. Por eso `paginate` sirve la página
que pide `?page=` o responde 404, en vez de corregir el valor en silencio a la primera o a la
última página: una URL que no corresponde a ninguna página no puede declararse canónica a sí
misma. La página que sirvió queda en la petición (`request.served_page`), y es lo único que lee
el procesador de la URL canónica (apps/site/context_processors.py).
"""

import re

from django.core.paginator import InvalidPage, Paginator
from django.http import Http404

PER_PAGE = 12

# Un número de página: dígitos ASCII, sin cero a la izquierda. `int()` acepta también «01», « 2»,
# «+2» y las cifras de otras escrituras («٢»), que serían otras tantas URL de la misma página.
PAGE_NUMBER = re.compile(r"[1-9][0-9]*")


def paginate(request, queryset, per_page=PER_PAGE):
    """La página de `queryset` que pide `?page=`, o la primera si no lo trae. Responde 404 si el
    valor no es un número de página o si esa página no existe."""
    number = request.GET.get("page", "1")
    if not PAGE_NUMBER.fullmatch(number):
        raise Http404
    try:
        page = Paginator(queryset, per_page).page(number)
    except InvalidPage:
        raise Http404 from None
    request.served_page = page.number
    return page
