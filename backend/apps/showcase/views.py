from django.shortcuts import get_object_or_404, render

from .models import Partner, PressMention, Publication


def _published():
    return Publication.objects.filter(published=True).select_related("publisher", "cover")


def publication_index(request):
    return render(
        request,
        "showcase/publication_index.html",
        {"publications": _published().prefetch_related("participants")},
    )


def publication_detail(request, slug):
    publication = get_object_or_404(
        _published().prefetch_related("participants", "where_to_buy"), slug=slug
    )
    return render(request, "showcase/publication_detail.html", {"publication": publication})


def press_index(request):
    mentions = PressMention.objects.filter(published=True).select_related("logo")
    return render(request, "showcase/press_index.html", {"mentions": mentions})


def partner_index(request):
    partners = Partner.objects.filter(active=True).select_related("logo")
    return render(request, "showcase/partner_index.html", {"partners": partners})
