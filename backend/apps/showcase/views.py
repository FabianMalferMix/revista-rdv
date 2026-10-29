from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.content.models import Article
from apps.content.pie import firmas, puerta, puertas_vecinas, vecinos_en_lista

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
    publication = get_object_or_404(
        _published().prefetch_related("participants", "where_to_buy"), slug=slug
    )
    pie = [puerta("Índice", "Todas las publicaciones", reverse("showcase:publication_index"))]
    if publication.publisher:
        pie.append(
            puerta(
                "Editorial",
                publication.publisher.name,
                reverse("reviews:publisher_detail", args=[publication.publisher.slug]),
            )
        )
    if publication.year:
        pie.append(
            puerta(
                "Trayectoria",
                str(publication.year),
                f"{reverse('agenda:trayectoria')}#anio-{publication.year}",
            )
        )
    pie += firmas(publication.participants.all())
    pie += puertas_vecinas(
        *vecinos_en_lista(_published(), publication), "Publicación", lambda p: p.title
    )
    # Las reseñas de la publicación: los textos que reseñan la obra que la representa
    # (`Work.publicacion`). Lo pidió el dueño del sitio después del paso 21 del plan.
    resenas = list(
        Article.objects.published()
        .filter(reviewed_works__publicacion=publication)
        .select_related("section", "cover_image")
        .prefetch_related("authors")
        .order_by("-published_at")
        .distinct()
    )
    return render(
        request,
        "showcase/publication_detail.html",
        {"publication": publication, "pie": pie, "resenas": resenas},
    )


def press_index(request):
    mentions = PressMention.objects.published().select_related("logo")
    return render(request, "showcase/press_index.html", {"mentions": mentions})


# El rótulo de cada grupo de aliados: el tipo, en plural.
GRUPOS_DE_ALIADOS = {
    Partner.Kind.FINANCIAMIENTO: "Financiamiento",
    Partner.Kind.INSTITUCION: "Instituciones",
    Partner.Kind.EDITORIAL: "Editoriales",
    Partner.Kind.MEDIO: "Medios",
    Partner.Kind.ESPACIO: "Espacios",
    Partner.Kind.OTRO: "Otros apoyos",
}


def partner_index(request):
    """Aliados agrupados por tipo, en el orden de los tipos: un fondo y una sala no son lo
    mismo para quien programa. Se agrupan en Python: una sola consulta."""
    partners = list(Partner.objects.published().select_related("logo"))
    grupos = [
        (rotulo, [p for p in partners if p.kind == kind])
        for kind, rotulo in GRUPOS_DE_ALIADOS.items()
        if any(p.kind == kind for p in partners)
    ]
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
    from apps.agenda.models import Event, Milestone
    from apps.agenda.services import cronologia, stats
    from apps.content.services import ultima_publicacion
    from apps.people.models import Contributor

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
