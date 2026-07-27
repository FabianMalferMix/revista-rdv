from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.showcase.models import SiteProfile

from .models import Event, Milestone


def stats():
    """Números de trayectoria (para /trayectoria/ y la portada)."""
    profile = SiteProfile.objects.first()
    past = Event.past()
    years = None
    if profile and profile.founded_year:
        years = max(timezone.now().year - profile.founded_year, 1)
    return {
        "years": years,
        "events": past.count(),
        "festivals": past.filter(type__in=[Event.Type.FESTIVAL, Event.Type.FERIA]).count(),
    }


def agenda(request):
    return render(request, "agenda/agenda.html", {"events": Event.upcoming()})


def trayectoria(request):
    past = Event.past().prefetch_related("participants")
    milestones = Milestone.objects.all()
    # Línea de tiempo agrupada por año, del más reciente al más antiguo.
    years = {}
    for event in past:
        years.setdefault(event.starts_at.year, {"events": [], "milestones": []})
        years[event.starts_at.year]["events"].append(event)
    for milestone in milestones:
        years.setdefault(milestone.year, {"events": [], "milestones": []})
        years[milestone.year]["milestones"].append(milestone)
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
