from django.shortcuts import render
from django.urls import reverse
from django.views.generic import RedirectView

from apps.agenda.models import Event, Milestone
from apps.agenda.services import cronologia, stats
from apps.content.models import Article
from apps.people.models import Contributor
from apps.site.pie import vecinos_en_lista
from apps.site.services import participants_prefetch, ultima_publicacion
from config import protected_media, publishing

from .models import Partner, PressMention, Publication, SiteProfile


def _published():
    return Publication.objects.published().select_related("publisher", "cover")


def publication_index(request):
    return render(
        request,
        "showcase/publication_index.html",
        {"publications": _published().prefetch_related("participants")},
    )


def publication_detail(request, slug):
    publication, preview = publishing.piece_for(
        request,
        Publication.objects.select_related("publisher", "cover").prefetch_related(
            participants_prefetch(), "where_to_buy"
        ),
        slug=slug,
    )
    # Las reseñas de la publicación: los textos que reseñan la obra que la representa
    # (`Work.publicacion`). Lo pidió el dueño del sitio después del paso 21 del plan.
    resenas = list(
        Article.objects.published()
        .for_row()
        .filter(reviewed_works__publicacion=publication)
        .order_by("-published_at")
        .distinct()
    )
    response = render(
        request,
        "showcase/publication_detail.html",
        {
            "publication": publication,
            "neighbors": vecinos_en_lista(_published(), publication),
            "resenas": resenas,
            "preview": preview,
        },
    )
    return publishing.marked_as_preview(response, preview)


def press_index(request):
    mentions = PressMention.objects.published().select_related("logo")
    return render(request, "showcase/press_index.html", {"mentions": mentions})


def partner_index(request):
    """Aliados agrupados por tipo, en el orden de los tipos: un fondo y una sala no son lo
    mismo para quien programa. Se agrupan en Python: una sola consulta."""
    partners = list(Partner.objects.published().select_related("logo"))
    by_kind = {kind: [] for kind in Partner.Kind}
    for partner in partners:
        kind = partner.kind if partner.kind in Partner.Kind.values else Partner.Kind.OTRO
        by_kind[kind].append(partner)
    grupos = [(kind, grupo) for kind, grupo in by_kind.items() if grupo]
    return render(request, "showcase/partner_index.html", {"partners": partners, "grupos": grupos})


def dossier(request):
    """Kit de prensa: página imprimible que agrega el contenido vivo del sitio.

    Un gestor cultural obtiene aquí —o en el PDF maquetado, si se subió— el
    resumen reenviable: quiénes son, qué han hecho, qué han publicado, qué ha
    dicho la prensa y cómo contactarlos. Fuente única: la base de datos.

    La trayectoria es una sola, por años y del más reciente al más antiguo: los hitos, las
    publicaciones y los ocho últimos eventos. Eran dos listas seguidas, y los años salían
    desordenados. Retratos, cubiertas y logos vienen en la consulta de su lista.
    """
    profile = SiteProfile.load()
    publicaciones = list(_published())
    return render(
        request,
        "showcase/dossier.html",
        {
            "profile": profile,
            "stats": stats(profile),
            "members": list(Contributor.objects.members()),
            "cronologia": cronologia(
                Event.objects.past()[:8], Milestone.objects.all(), publicaciones
            ),
            "publications": publicaciones,
            "mentions": PressMention.objects.published().exclude(quote=""),
            "partners": Partner.objects.published().select_related("logo"),
            "ultima_publicacion": ultima_publicacion(),
        },
    )


def dossier_pdf(request):
    """El dossier maquetado, en una dirección que no cambia al reemplazarlo: es lo que un gestor
    reenvía."""
    return protected_media.serve_current(request, SiteProfile.load().dossier_pdf, preview=False)


def publication_pdf(request, slug):
    publication, preview = publishing.piece_for(request, Publication.objects, slug=slug)
    return protected_media.serve_current(request, publication.pdf, preview)


class OldPublicationPdf(RedirectView):
    """La dirección anterior, con el nombre del archivo: lleva a la fija, sea cual sea el
    nombre, porque ya se repartió."""

    permanent = True

    def get_redirect_url(self, slug, filename):
        return reverse("showcase:publication_pdf", args=[slug])
