"""Servicios de dominio de la agenda: lógica reutilizable entre apps.

Se importa desde otras apps (portada, dossier) en vez de la capa de vistas, para no
acoplar `content`/`showcase` al módulo de vistas de `agenda`.
"""

from django.utils import timezone

from apps.showcase.models import Publication, SiteProfile

from .models import Event


def stats():
    """Números de trayectoria (para /trayectoria/, la portada y el dossier)."""
    profile = SiteProfile.load()
    past = Event.past()
    years = None
    if profile.founded_year:
        years = max(timezone.now().year - profile.founded_year, 1)
    return {
        "years": years,
        "events": past.count(),
        "festivals": past.filter(type__in=[Event.Type.FESTIVAL, Event.Type.FERIA]).count(),
        "publications": Publication.objects.filter(published=True).count(),
    }
