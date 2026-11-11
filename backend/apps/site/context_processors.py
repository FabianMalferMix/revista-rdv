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
    que ensuciaría la señal de canonicalización. Preserva solo ?page= en listados
    paginados, donde cada página es un recurso distinto."""
    url = absolute_url(request.path)
    page = request.GET.get("page", "")
    if page.isdigit() and page != "1":
        url = f"{url}?page={page}"
    return {"canonical_url": url}
