from .models import SiteProfile


def site_profile(request):
    """Expone el perfil del colectivo (o None si aún no existe) a todas las plantillas."""
    return {"site_profile": SiteProfile.objects.first()}
