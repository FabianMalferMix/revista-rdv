from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_safe

from apps.people.models import Contributor, url_for_person
from apps.reviews.models import Work
from apps.site.pie import vecinos
from config import publishing
from config.pagination import paginate

from .models import (
    Article,
    Collection,
    CollectionArticle,
    CollectionPoem,
    Page,
    Poem,
    Section,
    Tag,
)


@require_safe
def text_archive(request):
    """Archivo completo de textos (reseñas, ensayos, entrevistas), paginado."""
    return render(
        request,
        "content/text_archive.html",
        {"articles": paginate(request, Article.objects.published().for_row())},
    )


@require_safe
def article_detail(request, slug):
    article, preview = publishing.piece_for(
        request,
        Article.objects.select_related("section", "cover_image").prefetch_related(
            Article.bylines_prefetch(),
            Prefetch(
                "reviewed_works",
                queryset=Work.objects.select_related("publisher", "cover_image").with_page(),
            ),
            "tags",
        ),
        slug=slug,
    )
    response = render(
        request,
        "content/article_detail.html",
        {
            "article": article,
            "neighbors": vecinos(Article.objects.published(), article),
            "preview": preview,
        },
    )
    return publishing.marked_as_preview(response, preview)


@require_safe
def section_detail(request, slug):
    section = get_object_or_404(Section, slug=slug)
    return render(
        request,
        "content/section_detail.html",
        {
            "section": section,
            "articles": paginate(
                request, Article.objects.published().for_row().filter(section=section)
            ),
        },
    )


@require_safe
def tag_detail(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    return render(
        request,
        "content/tag_detail.html",
        {
            "tag": tag,
            "articles": paginate(request, Article.objects.published().for_row().filter(tags=tag)),
        },
    )


@require_safe
def contributor_detail(request, slug):
    contributor = get_object_or_404(Contributor.objects.visible(), slug=slug)
    if contributor.is_member:
        # URL canónica única por persona: el integrante vive en su perfil rico.
        return redirect(url_for_person(slug, is_member=True))
    return render(
        request,
        "content/contributor_detail.html",
        {
            "contributor": contributor,
            "poems": Poem.objects.published().for_row().filter(authors=contributor),
            "articles": paginate(
                request, Article.objects.published().for_row().filter(authors=contributor)
            ),
        },
    )


@require_safe
def collection_index(request):
    collections = Collection.objects.published()
    return render(request, "content/collection_index.html", {"collections": collections})


@require_safe
def poem_index(request):
    return render(
        request,
        "content/poem_index.html",
        {"poems": paginate(request, Poem.objects.published().for_row())},
    )


@require_safe
def poem_detail(request, slug):
    poem, preview = publishing.piece_for(
        request,
        Poem.objects.select_related("recording").prefetch_related(Poem.bylines_prefetch()),
        slug=slug,
    )
    response = render(
        request,
        "content/poem_detail.html",
        {
            "poem": poem,
            "colecciones": Collection.objects.published().filter(poems=poem).order_by("title"),
            "neighbors": vecinos(Poem.objects.published(), poem),
            "preview": preview,
        },
    )
    return publishing.marked_as_preview(response, preview)


@require_safe
def collection_detail(request, slug):
    collection, preview = publishing.piece_for(request, Collection.objects.all(), slug=slug)
    # Secuencia curada única: artículos y poemas publicados, mezclados por `position`. Cada pieza
    # llega con lo que pinta su fila.
    article_links = CollectionArticle.objects.filter(
        collection=collection, article__in=Article.objects.published()
    ).prefetch_related(Prefetch("article", queryset=Article.objects.published().for_row()))
    poem_links = CollectionPoem.objects.filter(
        collection=collection, poem__in=Poem.objects.published()
    ).prefetch_related(Prefetch("poem", queryset=Poem.objects.published().for_row()))
    entries = [("article", link.position, link.article) for link in article_links]
    entries += [("poem", link.position, link.poem) for link in poem_links]
    items = [{"kind": kind, "object": obj} for kind, _, obj in sorted(entries, key=lambda e: e[1])]
    response = render(
        request,
        "content/collection_detail.html",
        {"collection": collection, "items": items, "preview": preview},
    )
    return publishing.marked_as_preview(response, preview)


@require_safe
def page_detail(request, slug):
    page, preview = publishing.piece_for(request, Page.objects.all(), slug=slug)
    response = render(request, "content/page_detail.html", {"page": page, "preview": preview})
    return publishing.marked_as_preview(response, preview)
