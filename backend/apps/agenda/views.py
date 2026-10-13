from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.content.pie import puerta, puertas_vecinas, vecinos
from apps.showcase.models import Publication

from .models import Event, Milestone
from .services import stats


def agenda(request):
    # `recientes` solo se evalúa si la plantilla lo usa, es decir, si no hay nada anunciado:
    # una agenda vacía enseña lo último que se hizo en vez de una página en blanco.
    return render(
        request,
        "agenda/agenda.html",
        {"events": Event.upcoming(), "recientes": Event.past()[:3]},
    )


def trayectoria(request):
    past = Event.past().prefetch_related("participants")
    milestones = Milestone.objects.all()
    publications = Publication.objects.filter(published=True, year__isnull=False)
    # Línea de tiempo agrupada por año, del más reciente al más antiguo.
    empty = {"events": [], "milestones": [], "publications": []}
    years = {}
    for event in past:
        years.setdefault(event.starts_at.year, {k: [] for k in empty})
        years[event.starts_at.year]["events"].append(event)
    for milestone in milestones:
        years.setdefault(milestone.year, {k: [] for k in empty})
        years[milestone.year]["milestones"].append(milestone)
    for publication in publications:
        years.setdefault(publication.year, {k: [] for k in empty})
        years[publication.year]["publications"].append(publication)
    timeline = [{"year": year, **years[year]} for year in sorted(years, reverse=True)]
    return render(request, "agenda/trayectoria.html", {"timeline": timeline, "stats": stats()})


def event_detail(request, slug):
    event = get_object_or_404(
        Event.objects.filter(published=True)
        .select_related("poster")
        .prefetch_related("participants", "photos__asset", "recordings"),
        slug=slug,
    )
    recordings = event.recordings.filter(published=True)
    if event.is_past:
        pie = [
            puerta(
                "Trayectoria",
                str(event.starts_at.year),
                f"{reverse('agenda:trayectoria')}#anio-{event.starts_at.year}",
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
