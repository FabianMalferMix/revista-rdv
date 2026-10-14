from django.utils.functional import SimpleLazyObject

from .models import SiteProfile


def site_profile(request):
    """Expone el perfil del colectivo a todas las plantillas.

    Usa load() (garantiza la fila singleton) en vez de .first(): en una BD recién
    levantada, .first() devolvía None y dejaba cabecera/pie/identidad en blanco.

    Las redes del colectivo van en una lista que se consulta una sola vez por página, y
    solo si alguien la usa: las piden los datos estructurados, el pie, el menú del
    teléfono y la cejilla de la portada, y cada `social_links.all` en una plantilla era
    una consulta más.
    """
    perfil = SiteProfile.load()
    redes = SimpleLazyObject(lambda: list(perfil.social_links.all()))
    return {
        "site_profile": perfil,
        "redes_del_colectivo": redes,
        # La cejilla de la portada lo nombra: sale de la misma lista, sin otra consulta.
        "instagram_del_colectivo": SimpleLazyObject(
            lambda: next((r for r in redes if r.platform.strip().lower() == "instagram"), None)
        ),
    }
