"""Conversión de URLs públicas (YouTube/Vimeo) a URLs embebibles en iframe."""

import re

from django import template

register = template.Library()

_YOUTUBE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{6,})")
_VIMEO = re.compile(r"vimeo\.com/(\d+)")


@register.filter
def embed_src(url):
    """URL de iframe para YouTube/Vimeo; cadena vacía si no se reconoce el proveedor."""
    if not url:
        return ""
    match = _YOUTUBE.search(url)
    if match:
        return f"https://www.youtube-nocookie.com/embed/{match.group(1)}"
    match = _VIMEO.search(url)
    if match:
        return f"https://player.vimeo.com/video/{match.group(1)}"
    return ""
