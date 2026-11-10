from django.core.paginator import Paginator
from django.shortcuts import render

from apps.content.models import Poem
from apps.site.pie import vecinos_en_lista
from apps.site.services import participants_prefetch
from config import protected_media, publishing

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
        Recording.objects.select_related("poster", "event").prefetch_related(
            participants_prefetch()
        ),
        slug=slug,
    )
    response = render(
        request,
        "media/recording_detail.html",
        {
            "recording": recording,
            "poems": list(Poem.objects.published().filter(recording=recording)),
            "neighbors": vecinos_en_lista(_published(), recording),
            "preview": preview,
        },
    )
    return publishing.marked_as_preview(response, preview)


def recording_file(request, slug, filename):
    recording, preview = publishing.piece_for(request, Recording.objects, slug=slug)
    return protected_media.serve(recording.file, filename, preview)
