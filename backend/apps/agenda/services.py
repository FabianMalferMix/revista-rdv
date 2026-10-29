"""Servicios de dominio de la agenda: lógica reutilizable entre apps.

Los usan /trayectoria/ y el dossier de `showcase`, que los importa de aquí y no de
`agenda.views`, para no depender de la capa de vistas de otra app.
"""

from django.db.models import Count, Q
from django.utils import timezone

from apps.showcase.models import Publication, SiteProfile

from .models import Event


def stats(perfil=None):
    """Números de trayectoria, para /trayectoria/ y el dossier.

    Actividades, festivales y ferias salen de una sola consulta. `festivals` suma
    festivales y ferias, como los rotula la trayectoria; el dossier los nombra por
    separado (`festivales`, `ferias`), porque «1 festival» no puede ser una feria.
    `perfil`: el que la vista ya cargó, para no pedirlo dos veces."""
    profile = perfil or SiteProfile.load()
    years = None
    if profile.founded_year:
        years = max(timezone.now().year - profile.founded_year, 1)
    cuentas = Event.objects.past().aggregate(
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
        "publications": Publication.objects.published().count(),
    }


def cronologia(eventos, hitos=(), publicaciones=()):
    """La trayectoria por años, del más reciente al más antiguo. En cada año, los hitos, las
    publicaciones y los eventos, en el orden en que llegan (los eventos, del más reciente
    al más antiguo). La usan /trayectoria/ y el dossier, que la armaba en dos listas
    seguidas —primero los hitos, después los eventos— y sus años no iban en orden.

    El año de un evento es el de su fecha en la hora local, la que enseña la página: un
    recital del 31 de diciembre a las 22:00 en Santiago es del año que termina, aunque en
    UTC ya sea el siguiente. Una publicación sin año no tiene dónde ir."""
    anios = {}

    def anio(numero):
        return anios.setdefault(
            numero, {"year": numero, "milestones": [], "publications": [], "events": []}
        )

    for hito in hitos:
        anio(hito.year)["milestones"].append(hito)
    for publicacion in publicaciones:
        if publicacion.year:
            anio(publicacion.year)["publications"].append(publicacion)
    for evento in eventos:
        anio(timezone.localtime(evento.starts_at).year)["events"].append(evento)
    return [anios[numero] for numero in sorted(anios, reverse=True)]
