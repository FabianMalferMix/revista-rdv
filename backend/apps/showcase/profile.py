"""El perfil del colectivo, leído una sola vez en cada petición."""

from .models import SiteProfile

# Lo que toda página lee del perfil: la imagen para compartir, que base.html usa cuando la
# pieza no tiene la suya (apps/media/templatetags/social.py). Viene en la misma consulta.
PAGE_RELATIONS = ("og_image",)

_ATTRIBUTE = "_site_profile"


def request_profile(request, *relations):
    """El perfil de esta petición: se carga la primera vez que alguien lo pide y se guarda en la
    petición, así que la vista, las plantillas (`site_profile`) y los feeds comparten la misma
    consulta.

    `relations` son claves de `select_related` con lo que la vista va a leer del perfil. Llegan
    las de quien lo pide primero: las vistas que leen relaciones lo piden antes de pintar, y el
    procesador de contexto, que es perezoso, lo encuentra ya cargado."""
    profile = getattr(request, _ATTRIBUTE, None)
    if profile is None:
        profile = SiteProfile.load(*PAGE_RELATIONS, *relations)
        setattr(request, _ATTRIBUTE, profile)
    return profile
