from django.shortcuts import get_object_or_404, render

from apps.content.models import Article
from apps.showcase.models import Publication

from .models import BookAuthor, Publisher, Work


def _reviews_of(work_ids):
    return (
        Article.objects.published()
        .filter(reviewed_works__in=work_ids)
        .select_related("section")
        .prefetch_related("authors")
        .distinct()
    )


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
        {"work": work, "articles": _reviews_of([work.id])},
    )


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
            "articles": _reviews_of(list(works.values_list("id", flat=True))),
        },
    )


def bookauthor_detail(request, slug):
    author = get_object_or_404(BookAuthor.objects.visible(), slug=slug)
    works = author.works.visible()
    return render(
        request,
        "reviews/bookauthor_detail.html",
        {
            "author": author,
            "works": works,
            "articles": _reviews_of(list(works.values_list("id", flat=True))),
        },
    )
