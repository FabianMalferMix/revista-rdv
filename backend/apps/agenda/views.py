from django.shortcuts import get_object_or_404, render

from apps.showcase.models import Publication

from .models import Event, Milestone
from .services import stats


def agenda(request):
    return render(request, "agenda/agenda.html", {"events": Event.upcoming()})


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
        Event.objects.filter(published=True).prefetch_related(
            "participants", "photos__asset", "recordings"
        ),
        slug=slug,
    )
    recordings = event.recordings.filter(published=True)
    return render(request, "agenda/event_detail.html", {"event": event, "recordings": recordings})


def gallery(request):
    events = (
        Event.objects.filter(published=True, photos__isnull=False)
        .distinct()
        .prefetch_related("photos__asset")
        .order_by("-starts_at")
    )
    return render(request, "agenda/gallery.html", {"events": events})
