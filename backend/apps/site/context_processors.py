"""Lo que el sitio da a todas las plantillas: la navegación, con lo actual marcado, y la URL
canónica de la página."""

from apps.site import navigation
from config.origin import absolute_url


def nav(request):
    """La navegación del sitio (apps/site/navigation.py), con lo actual marcado: la barra, la
    sub-fila de la página y el mapa del pie y del menú del teléfono. En el dossier, lo marca su
    botón, que está fuera de la barra."""
    vista = getattr(getattr(request, "resolver_match", None), "view_name", "") or ""
    return {
        "nav_principal": navigation.bar(vista),
        "subnav": navigation.subnav(vista),
        "mapa": navigation.site_map(),
        "dossier_actual": vista == "showcase:dossier",
    }


def canonical(request):
    """URL canónica: el origen fijo (SITE_URL) y la ruta, SIN el query string (utm_*, q, …)
    que ensuciaría la señal de canonicalización. En un listado paginado cada página es un
    recurso distinto: la canónica lleva `?page=N` si la vista sirvió la página N
    (`config.pagination.paginate`), y la primera no lo lleva."""
    url = absolute_url(request.path)
    page = getattr(request, "served_page", None)
    if page is not None and page > 1:
        url = f"{url}?page={page}"
    return {"canonical_url": url}
