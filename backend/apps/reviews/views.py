from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from apps.content.models import Article
from apps.showcase.models import Publication
from config.pagination import paginate

from .models import BookAuthor, Publisher, Work


def _reviews_of(request, work_ids):
    """Los textos que reseñan esas obras, de 12 en 12 como los demás índices de textos."""
    reviews = Article.objects.published().for_row().filter(reviewed_works__in=work_ids).distinct()
    return paginate(request, reviews)


@require_safe
def work_detail(request, slug):
    work = get_object_or_404(
        # Con su publicación del colectivo, si la tiene: la cabecera enlaza a ella.
        Work.objects.visible()
        .select_related("publisher", "publicacion")
        .prefetch_related("authors"),
        slug=slug,
    )
    return render(
        request,
        "reviews/work_detail.html",
        {"work": work, "articles": _reviews_of(request, [work.id])},
    )


@require_safe
def publisher_detail(request, slug):
    publisher = get_object_or_404(Publisher.objects.visible(), slug=slug)
    # Las publicaciones del colectivo con esta editorial, y aparte las demás obras visibles: la
    # obra que es una publicación del colectivo ya sale con ella.
    publications = list(
        Publication.objects.published().filter(publisher=publisher).select_related("cover")
    )
    works = publisher.works.visible()
    return render(
        request,
        "reviews/publisher_detail.html",
        {
            "publisher": publisher,
            "publications": publications,
            "works": works.exclude(publicacion__in=publications),
            "articles": _reviews_of(request, list(works.values_list("id", flat=True))),
        },
    )


@require_safe
def bookauthor_detail(request, slug):
    author = get_object_or_404(BookAuthor.objects.visible(), slug=slug)
    works = author.works.visible()
    return render(
        request,
        "reviews/bookauthor_detail.html",
        {
            "author": author,
            "works": works,
            "articles": _reviews_of(request, list(works.values_list("id", flat=True))),
        },
    )
