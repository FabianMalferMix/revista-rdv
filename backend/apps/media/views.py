from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse

from apps.content.models import Poem
from apps.content.pie import puerta, puertas_vecinas, vecinos_en_lista
from config import publishing

from .models import Recording


def _published():
    return Recording.objects.published().select_related("poster", "event")


def recording_index(request):
    recordings = _published().prefetch_related("participants")
    page = Paginator(recordings, 12).get_page(request.GET.get("page"))
    return render(request, "media/recording_index.html", {"recordings": page})


def recording_detail(request, slug):
    recording, preview = publishing.piece_for(
        request,
        Recording.objects.select_related("poster", "event").prefetch_related("participants"),
        slug=slug,
    )
    pie = [puerta("Índice", "Todos los registros", reverse("media:recording_index"))]
    pie += [
        puerta("Poema registrado", p.title, p.get_absolute_url())
        for p in Poem.objects.published().filter(recording=recording)
    ]
    if evento := recording.public_event:
        pie.append(puerta("Evento", evento.title, evento.get_absolute_url()))
    pie += puertas_vecinas(
        *vecinos_en_lista(_published(), recording), "Registro", lambda r: r.title
    )
    response = render(
        request,
        "media/recording_detail.html",
        {"recording": recording, "pie": pie, "preview": preview},
    )
    return publishing.marked_as_preview(response, preview)
