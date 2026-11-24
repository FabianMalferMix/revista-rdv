"""La lupa de la cabecera (base.html)."""

from django import template

from apps.site.views import SEARCH_PANEL

register = template.Library()


@register.simple_tag
def search_panel_id():
    """El id del panel de resultados de la lupa. htmx pone ahí lo que trae y lo manda en
    HX-Target, y la vista de búsqueda devuelve el fragmento del panel solo a ese destino."""
    return SEARCH_PANEL
