"""Etiqueta para renderizar imágenes responsivas (srcset + width/height + lazy)."""

from django import template

register = template.Library()


@register.inclusion_tag("media/partials/_responsive_img.html")
def responsive_img(asset, sizes="100vw", css_class="", lazy=True, alt=None):
    """Renderiza un <img> con srcset (si hay derivados), width/height (anti-CLS) y
    decoding async. `lazy=False` para imágenes destacadas sobre el pliegue (LCP)."""
    return {
        "url": asset.file.url,
        "srcset": asset.srcset(),
        "sizes": sizes,
        "width": asset.width,
        "height": asset.height,
        "alt": alt or asset.alt_text,
        "css_class": css_class,
        "lazy": lazy,
    }
