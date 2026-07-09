from django.shortcuts import get_object_or_404, render

from apps.content.models import Article, ArticleStatus

from .models import BookAuthor, Publisher, Work


def _reviews_of(work_ids):
    return (
        Article.objects.filter(
            status=ArticleStatus.PUBLISHED, reviewed_works__in=work_ids
        )
        .select_related("section")
        .prefetch_related("authors")
        .distinct()
    )


def work_detail(request, slug):
    work = get_object_or_404(
        Work.objects.select_related("publisher").prefetch_related("authors"), slug=slug
    )
    return render(
        request,
        "reviews/work_detail.html",
        {"work": work, "articles": _reviews_of([work.id])},
    )


def publisher_detail(request, slug):
    publisher = get_object_or_404(Publisher, slug=slug)
    works = publisher.works.all()
    return render(
        request,
        "reviews/publisher_detail.html",
        {
            "publisher": publisher,
            "works": works,
            "articles": _reviews_of(list(works.values_list("id", flat=True))),
        },
    )


def bookauthor_detail(request, slug):
    author = get_object_or_404(BookAuthor, slug=slug)
    works = author.works.all()
    return render(
        request,
        "reviews/bookauthor_detail.html",
        {
            "author": author,
            "works": works,
            "articles": _reviews_of(list(works.values_list("id", flat=True))),
        },
    )
