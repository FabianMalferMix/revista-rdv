from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render

from apps.site.pie import vecinos_en_lista

from .models import Contributor, url_for_person


def member_index(request):
    return render(request, "people/member_index.html", {"members": Contributor.objects.members()})


def member_detail(request, slug):
    # Los integrantes históricos (active=False) conservan su perfil accesible.
    member = Contributor.objects.select_related("photo").filter(slug=slug, is_member=True).first()
    if member is None:
        # Quien deja de figurar como integrante sigue en /colaborador/ si tiene ficha pública,
        # y la dirección que ya circula lleva hasta ella. Con un 302 y no un 301: la membresía
        # puede volver a cambiar, y dos 301 guardados en el navegador acabarían en un bucle.
        if Contributor.objects.visible().filter(slug=slug).exists():
            return redirect(url_for_person(slug, is_member=False))
        raise Http404
    articles = member.articles.published().for_row().order_by("-published_at")
    poems = member.poems.published().for_row().order_by("-published_at")
    recordings = member.recordings.published()
    # Las actividades en que participó (ticket 4.5): la ficha enseñaba lo que escribe y lo
    # que grabó, pero no dónde ha leído. Las doce más recientes; el resto, en la trayectoria.
    actividades = member.events.published().order_by("-starts_at")[:12]
    return render(
        request,
        "people/member_detail.html",
        {
            "member": member,
            "articles": Paginator(articles, 12).get_page(request.GET.get("page")),
            "poems": poems,
            "recordings": recordings,
            "actividades": actividades,
            "neighbors": vecinos_en_lista(Contributor.objects.members(), member),
        },
    )
