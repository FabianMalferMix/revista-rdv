from .models import Section


def nav(request):
    """Secciones para el menú de navegación, disponibles en todas las plantillas."""
    return {"nav_sections": Section.objects.all()}


def canonical(request):
    """URL canónica: esquema + host + ruta, SIN el query string (utm_*, q, …) que
    ensuciaría la señal de canonicalización. Preserva solo ?page= en listados
    paginados, donde cada página es un recurso distinto (hallazgo #06)."""
    url = f"{request.scheme}://{request.get_host()}{request.path}"
    page = request.GET.get("page", "")
    if page.isdigit() and page != "1":
        url = f"{url}?page={page}"
    return {"canonical_url": url}
