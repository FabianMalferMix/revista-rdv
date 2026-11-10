"""La tapa de una publicación, la misma en su ficha, el catálogo, el dossier y el estante de la
portada."""

from django import template

register = template.Library()


@register.inclusion_tag("partials/_tapa.html")
def cover(publication, sizes, css_class="", lazy=True, decorative=False):
    """La cubierta de `publication` o, sin ella, su título impreso en una caja del mismo tamaño.
    `sizes`, `css_class`, `lazy` y `decorative` son los de `responsive_img`; la caja lleva la
    misma clase que la cubierta."""
    return {
        "pub": publication,
        "sizes": sizes,
        "css_class": css_class,
        "lazy": lazy,
        "decorative": decorative,
    }
