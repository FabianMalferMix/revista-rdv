"""Sanitización de HTML autoral (cierra el riesgo del `|safe` en plantillas).

Las listas y la regla de las imágenes son las de `config/content_policy.py`, las mismas que recibe
el editor del panel.
"""

import re

import nh3

from config.content_policy import (
    ALLOWED_ATTRIBUTES,
    ALLOWED_TAGS,
    ALLOWED_URL_SCHEMES,
    is_own_url,
)

# Una etiqueta tal como la escribe nh3: los valores de sus atributos van entre comillas dobles, y
# dentro de un valor las comillas y los signos < y > van escapados, así que «[^>]*» no se sale de la
# etiqueta y « src="» solo puede ser el atributo.
_IMG = re.compile(r"<img\b[^>]*>")
# Un enlace o una figura sin nada dentro: lo que queda de una imagen de fuera que iba enlazada o
# con su marco. Un enlace vacío no se ve, pero el teclado y el lector de pantalla se detienen en él.
_EMPTY_WRAPPER = re.compile(r"<(a|figure)\b[^>]*>\s*</\1>")


def _keep_own_image_sources(tag, attribute, value):
    """El `src` de una imagen pasa solo si es del propio sitio."""
    if tag == "img" and attribute == "src" and not is_own_url(value):
        return None
    return value


def _drop_images_without_source(html):
    """Quita entera cada imagen que se quedó sin `src` (la de fuera o la que solo traía `srcset`),
    y luego el enlace o la figura que la contenía si no les queda nada."""
    html = _IMG.sub(lambda match: match[0] if ' src="' in match[0] else "", html)
    while (emptied := _EMPTY_WRAPPER.sub("", html)) != html:
        html = emptied
    return html


def clean_html(html):
    """Devuelve el HTML depurado según la lista blanca. Idempotente."""
    if not html:
        return html
    cleaned = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_keep_own_image_sources,
        clean_content_tags={"script", "style"},
        link_rel="nofollow noopener noreferrer",
        url_schemes=ALLOWED_URL_SCHEMES,
    )
    return _drop_images_without_source(cleaned)
