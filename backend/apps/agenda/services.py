"""Servicios de dominio de la agenda: lógica reutilizable entre apps.

Se importa desde otras apps (portada, dossier) en vez de la capa de vistas, para no
acoplar `content`/`showcase` al módulo de vistas de `agenda`.
"""

from django.db.models import Count, Q
from django.utils import timezone

from apps.showcase.models import Publication, SiteProfile

from .models import Event


def stats():
    """Números de trayectoria (para /trayectoria/, la portada y el dossier).

    Actividades, festivales y ferias salen de una sola consulta (eran dos). `festivals`
    suma festivales y ferias, como los rotulan la trayectoria y el dossier; la portada los
    nombra por separado, porque «1 festival» no puede ser una feria."""
    profile = SiteProfile.load()
    years = None
    if profile.founded_year:
        years = max(timezone.now().year - profile.founded_year, 1)
    cuentas = Event.past().aggregate(
        events=Count("pk"),
        festivales=Count("pk", filter=Q(type=Event.Type.FESTIVAL)),
        ferias=Count("pk", filter=Q(type=Event.Type.FERIA)),
    )
    return {
        "years": years,
        "events": cuentas["events"],
        "festivals": cuentas["festivales"] + cuentas["ferias"],
        "festivales": cuentas["festivales"],
        "ferias": cuentas["ferias"],
        "publications": Publication.objects.filter(published=True).count(),
    }
