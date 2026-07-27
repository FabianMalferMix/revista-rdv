from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Recording


def _published():
    return Recording.objects.filter(published=True).select_related("poster", "event")


def recording_index(request):
    recordings = _published().prefetch_related("participants")
    page = Paginator(recordings, 12).get_page(request.GET.get("page"))
    return render(request, "media/recording_index.html", {"recordings": page})


def recording_detail(request, slug):
    recording = get_object_or_404(_published().prefetch_related("participants"), slug=slug)
    return render(request, "media/recording_detail.html", {"recording": recording})
