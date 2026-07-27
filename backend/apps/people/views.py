from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.content.models import EditorialStatus

from .models import Contributor


def member_index(request):
    return render(request, "people/member_index.html", {"members": Contributor.members()})


def member_detail(request, slug):
    # Los integrantes históricos (active=False) conservan su perfil accesible.
    member = get_object_or_404(Contributor, slug=slug, is_member=True)
    articles = (
        member.articles.filter(status=EditorialStatus.PUBLISHED)
        .select_related("section")
        .prefetch_related("authors")
        .order_by("-published_at")
    )
    poems = (
        member.poems.filter(status=EditorialStatus.PUBLISHED)
        .prefetch_related("authors")
        .order_by("-published_at")
    )
    recordings = member.recordings.filter(published=True)
    return render(
        request,
        "people/member_detail.html",
        {
            "member": member,
            "articles": Paginator(articles, 12).get_page(request.GET.get("page")),
            "poems": poems,
            "recordings": recordings,
        },
    )
