"""La imagen para compartir de cada página: `og:image`, `twitter:card` y la del JSON-LD.

Cada modelo con ficha dice cuál es la suya con `social_image()`; si no tiene, se usa la del
perfil del sitio. La tarjeta es grande siempre que haya imagen, propia o del perfil.
"""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def social_image_url(context, obj=None):
    """La URL absoluta de la imagen para compartir `obj` (o el sitio, sin `obj`); vacía si
    no hay ninguna."""
    imagen = obj.social_image() if obj is not None else None
    imagen = imagen or getattr(context.get("site_profile"), "og_image", None)
    return context["request"].build_absolute_uri(imagen.file.url) if imagen else ""


@register.inclusion_tag("partials/_social_meta.html", takes_context=True)
def social_meta(context, obj=None):
    """Las metas `og:image` y `twitter:card` de la página."""
    return {"image_url": social_image_url(context, obj)}
