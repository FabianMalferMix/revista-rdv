from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.content.models import EditorialStatus
from apps.content.pie import puerta, puertas_vecinas, vecinos_en_lista

from .models import Contributor


def member_index(request):
    return render(request, "people/member_index.html", {"members": Contributor.members()})


def member_detail(request, slug):
    # Los integrantes históricos (active=False) conservan su perfil accesible.
    member = get_object_or_404(
        Contributor.objects.select_related("photo"), slug=slug, is_member=True
    )
    articles = (
        member.articles.filter(status=EditorialStatus.PUBLISHED)
        .select_related("section")
        .prefetch_related("authors")
        .order_by("-published_at")
    )
    # select_related("recording"): la fila del poema avisa «con registro».
    poems = (
        member.poems.filter(status=EditorialStatus.PUBLISHED)
        .select_related("recording")
        .prefetch_related("authors")
        .order_by("-published_at")
    )
    recordings = member.recordings.filter(published=True)
    # Las actividades en que participó (ticket 4.5): la ficha enseñaba lo que escribe y lo
    # que grabó, pero no dónde ha leído. Las doce más recientes; el resto, en la trayectoria.
    actividades = member.events.filter(published=True).order_by("-starts_at")[:12]
    return render(
        request,
        "people/member_detail.html",
        {
            "member": member,
            "articles": Paginator(articles, 12).get_page(request.GET.get("page")),
            "poems": poems,
            "recordings": recordings,
            "actividades": actividades,
            "pie": [
                puerta("Índice", "Todo el colectivo", reverse("people:member_index")),
                *puertas_vecinas(
                    *vecinos_en_lista(Contributor.members(), member),
                    "Integrante",
                    lambda c: c.display_name,
                ),
                puerta("El colectivo", "Trayectoria", reverse("agenda:trayectoria")),
                puerta("Para programar", "Dossier", reverse("showcase:dossier")),
            ],
        },
    )
