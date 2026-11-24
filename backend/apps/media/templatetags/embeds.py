"""El reproductor de un registro con enlace: los proveedores de `config/content_policy.py`."""

from urllib.parse import quote

from django import template
from django.urls import reverse

from apps.content.legal import PLAYERS_HEADING
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


@register.simple_tag
def players_policy_url():
    """La sección de la política de cookies que explica los reproductores. El titular no tiene
    `id` (el saneo del HTML de autor no lo admite), así que se llega a él con un fragmento de
    texto (`#:~:text=`), codificado entero; los navegadores que no lo entienden abren la página
    por arriba."""
    page = reverse("content:page_detail", args=["cookies"])
    return f"{page}#:~:text={quote(PLAYERS_HEADING, safe='')}"
