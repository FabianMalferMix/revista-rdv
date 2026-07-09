"""Sanitización de HTML autoral (cierra el riesgo del `|safe` en plantillas)."""
import nh3

# Etiquetas permitidas para el cuerpo de artículos y páginas.
ALLOWED_TAGS = {
    "p", "br", "hr", "blockquote", "pre", "code",
    "em", "strong", "i", "b", "u", "s", "sub", "sup", "small", "cite",
    "h2", "h3", "h4",
    "ul", "ol", "li",
    "a", "img", "figure", "figcaption",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
}


def clean_html(html):
    """Devuelve el HTML depurado según la lista blanca. Idempotente."""
    if not html:
        return html
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        clean_content_tags={"script", "style"},
        link_rel="nofollow noopener noreferrer",
    )
