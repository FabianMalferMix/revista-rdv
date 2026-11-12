from django.db.models import Count, Prefetch
from django.shortcuts import render
from django.views.decorators.http import require_safe

from apps.showcase.models import Publication
from apps.showcase.profile import request_profile
from apps.site.pie import vecinos
from apps.site.services import participants_prefetch
from config import publishing
from config.pagination import paginate

from .models import Event, EventPhoto, Milestone
from .services import cronologia, stats

# Las fotos de la hoja de contactos de cada álbum en la galería: la primera a doble tamaño y dos
# a su lado (agenda/gallery.html y `.hoja` en componentes.css).
ALBUM_SHEET_PHOTOS = 3


@require_safe
def agenda(request):
    # `recientes` solo se evalúa si la plantilla lo usa, es decir, si no hay nada anunciado:
    # una agenda vacía enseña lo último que se hizo en vez de una página en blanco.
    return render(
        request,
        "agenda/agenda.html",
        {"events": Event.objects.upcoming(), "recientes": Event.objects.past()[:3]},
    )


@require_safe
def trayectoria(request):
    # Línea de tiempo agrupada por año, del más reciente al más antiguo. La editorial de
    # cada publicación viene en la misma consulta: la fila la nombra.
    timeline = cronologia(
        Event.objects.past(),
        Milestone.objects.all(),
        Publication.objects.published().filter(year__isnull=False).select_related("publisher"),
    )
    return render(
        request,
        "agenda/trayectoria.html",
        {"timeline": timeline, "stats": stats(request_profile(request))},
    )


@require_safe
def event_detail(request, slug):
    event, preview = publishing.piece_for(
        request,
        Event.objects.select_related("poster").prefetch_related(
            participants_prefetch(), "photos__asset", "recordings"
        ),
        slug=slug,
    )
    # Los registros publicados salen de la caché del prefetch: un `.filter()` la saltaba y
    # hacía una consulta más.
    recordings = [r for r in event.recordings.all() if r.published]
    # Las actividades van por fecha: «anterior» es la de antes en el tiempo. `vecinos`
    # devuelve el orden de un índice, del más reciente al más antiguo: se dan vuelta.
    mas_reciente, mas_antigua = vecinos(Event.objects.published(), event, "starts_at")
    # Quién hizo las fotos, una vez bajo el álbum; cada foto lo repite en su vista ampliada.
    # Sale de la caché del prefetch (photos__asset): no añade consultas.
    creditos = sorted({p.asset.credit for p in event.photos.all() if p.asset.credit})
    response = render(
        request,
        "agenda/event_detail.html",
        {
            "event": event,
            "recordings": recordings,
            "neighbors": (mas_antigua, mas_reciente),
            "creditos": creditos,
            "preview": preview,
        },
    )
    return publishing.marked_as_preview(response, preview)


@require_safe
def gallery(request):
    # De cada álbum llegan solo las fotos de su hoja (el corte va en la consulta de la precarga),
    # y cuántas tiene en total, contadas en la consulta de la lista.
    events = (
        Event.objects.published()
        .annotate(photo_count=Count("photos"))
        .filter(photo_count__gt=0)
        .prefetch_related(
            Prefetch(
                "photos",
                queryset=EventPhoto.objects.select_related("asset")[:ALBUM_SHEET_PHOTOS],
                to_attr="sheet_photos",
            )
        )
        .order_by("-starts_at", "-pk")
    )
    return render(request, "agenda/gallery.html", {"events": paginate(request, events)})
