"""El reproductor de un registro con enlace: los proveedores de `config/content_policy.py`."""

from django import template

from config.content_policy import embed_provider_for

register = template.Library()


@register.filter
def embed_src(url):
    """La dirección del reproductor para el iframe; vacía si no se reconoce el proveedor."""
    provider = embed_provider_for(url)
    return provider.src(url) if provider else ""


@register.filter
def embed_provider(url):
    """El nombre del proveedor, para avisar a quién se conecta el visitante antes de que ocurra.
    Vacío si no se reconoce."""
    provider = embed_provider_for(url)
    return provider.name if provider else ""
