"""Sanitización de HTML autoral (cierra el riesgo del `|safe` en plantillas)."""

import nh3

# Etiquetas permitidas para el cuerpo de artículos y páginas.
ALLOWED_TAGS = {
    "p",
    "br",
    "hr",
    "blockquote",
    "pre",
    "code",
    "em",
    "strong",
    "i",
    "b",
    "u",
    "s",
    "sub",
    "sup",
    "small",
    "cite",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "figure",
    "figcaption",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
}

# Protocolos admitidos en href/src. Se fijan EXPLÍCITAMENTE en vez de heredar el default
# de nh3, que permite 25 esquemas —entre ellos ssh, magnet, bitcoin, sms o wtai— que este
# sitio no necesita y que podrían cambiar con una versión de la librería. Los peligrosos
# (javascript:, data:, vbscript:) ya los descartaba nh3; esto añade el resto.
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


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
        url_schemes=ALLOWED_URL_SCHEMES,
    )
