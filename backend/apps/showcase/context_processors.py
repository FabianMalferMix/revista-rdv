from django.utils.functional import SimpleLazyObject

from .models import SiteProfile


def site_profile(request):
    """Expone el perfil del colectivo a todas las plantillas.

    Usa load() (garantiza la fila singleton) en vez de .first(): en una BD recién
    levantada, .first() devolvía None y dejaba cabecera/pie/identidad en blanco.

    Las redes del colectivo van en una lista que se consulta una sola vez por página, y
    solo si alguien la usa: las piden los datos estructurados, el pie y el menú del
    teléfono, y cada `social_links.all` en una plantilla era una consulta más.
    """
    perfil = SiteProfile.load()
    return {
        "site_profile": perfil,
        "redes_del_colectivo": SimpleLazyObject(lambda: list(perfil.social_links.all())),
    }
