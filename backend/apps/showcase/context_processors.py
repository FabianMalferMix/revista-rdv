from .models import SiteProfile


def site_profile(request):
    """Expone el perfil del colectivo a todas las plantillas.

    Usa load() (garantiza la fila singleton) en vez de .first(): en una BD recién
    levantada, .first() devolvía None y dejaba cabecera/pie/identidad en blanco.
    """
    return {"site_profile": SiteProfile.load()}
