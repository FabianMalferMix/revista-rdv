from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from apps.content.pie import puerta, puertas_vecinas, vecinos
from apps.showcase.models import Publication

from .models import Event, Milestone
from .services import cronologia, stats


def agenda(request):
    # `recientes` solo se evalúa si la plantilla lo usa, es decir, si no hay nada anunciado:
    # una agenda vacía enseña lo último que se hizo en vez de una página en blanco.
    return render(
        request,
        "agenda/agenda.html",
        {"events": Event.upcoming(), "recientes": Event.past()[:3]},
    )


def trayectoria(request):
    # Línea de tiempo agrupada por año, del más reciente al más antiguo. La editorial de
    # cada publicación viene en la misma consulta: la fila la nombra.
    timeline = cronologia(
        Event.past(),
        Milestone.objects.all(),
        Publication.objects.filter(published=True, year__isnull=False).select_related("publisher"),
    )
    return render(request, "agenda/trayectoria.html", {"timeline": timeline, "stats": stats()})


def event_detail(request, slug):
    event = get_object_or_404(
        Event.objects.filter(published=True)
        .select_related("poster")
        .prefetch_related("participants", "photos__asset", "recordings"),
        slug=slug,
    )
    # Los registros publicados salen de la caché del prefetch: un `.filter()` la saltaba y
    # hacía una consulta más.
    recordings = [r for r in event.recordings.all() if r.published]
    if event.is_past:
        pie = [
            puerta(
                "Trayectoria",
                str(timezone.localtime(event.starts_at).year),
                f"{reverse('agenda:trayectoria')}#anio-{timezone.localtime(event.starts_at).year}",
            )
        ]
    else:
        pie = [puerta("Índice", "Agenda", reverse("agenda:agenda"))]
    if event.photos.all():
        pie.append(puerta("Fotos", "Galería", reverse("agenda:gallery")))
    pie.append(puerta("Para programar", "Dossier", reverse("showcase:dossier")))
    # Las actividades van por fecha: «anterior» es la de antes en el tiempo. `vecinos`
    # devuelve el orden de un índice, del más reciente al más antiguo: se dan vuelta.
    mas_reciente, mas_antigua = vecinos(Event.objects.filter(published=True), event, "starts_at")
    pie += puertas_vecinas(mas_antigua, mas_reciente, "Actividad", lambda e: e.title)
    # Quién hizo las fotos, una vez bajo el álbum; cada foto lo repite en su vista ampliada.
    # Sale de la caché del prefetch (photos__asset): no añade consultas.
    creditos = sorted({p.asset.credit for p in event.photos.all() if p.asset.credit})
    return render(
        request,
        "agenda/event_detail.html",
        {"event": event, "recordings": recordings, "pie": pie, "creditos": creditos},
    )


def gallery(request):
    events = (
        Event.objects.filter(published=True, photos__isnull=False)
        .distinct()
        .prefetch_related("photos__asset")
        .order_by("-starts_at")
    )
    return render(request, "agenda/gallery.html", {"events": events})
