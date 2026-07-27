from django.shortcuts import get_object_or_404, render

from .models import Partner, PressMention, Publication, SiteProfile


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


def dossier(request):
    """Kit de prensa: página imprimible que agrega el contenido vivo del sitio.

    Un gestor cultural obtiene aquí —o en el PDF maquetado, si se subió— el
    resumen reenviable: quiénes son, qué han hecho, qué han publicado, qué ha
    dicho la prensa y cómo contactarlos. Fuente única: la base de datos.
    """
    from apps.agenda.models import Event, Milestone
    from apps.agenda.views import stats
    from apps.people.models import Contributor

    profile = SiteProfile.load()
    return render(
        request,
        "showcase/dossier.html",
        {
            "profile": profile,
            "stats": stats(),
            "members": Contributor.members(),
            "events": Event.past().prefetch_related("participants")[:8],
            "milestones": Milestone.objects.all(),
            "publications": _published().prefetch_related("participants"),
            "mentions": PressMention.objects.filter(published=True).exclude(quote=""),
            "partners": Partner.objects.filter(active=True),
        },
    )
