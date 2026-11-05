from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.people.models import Contributor, url_for_person
from apps.reviews.models import Work
from apps.site.pie import firmas, puerta, puertas_vecinas, vecinos
from config import publishing

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


def _published():
    # cover_image: la fila de cada texto enseña su imagen en miniatura.
    return (
        Article.objects.published()
        .select_related("section", "cover_image")
        .prefetch_related(Article.bylines_prefetch())
    )


def _published_poems():
    # select_related("recording"): `published_recording` lo consulta en las fichas y en
    # las tarjetas de los listados; sin esto sería una consulta por poema.
    return (
        Poem.objects.published()
        .select_related("recording")
        .prefetch_related(Poem.bylines_prefetch())
    )


def _paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def text_archive(request):
    """Archivo completo de textos (reseñas, ensayos, entrevistas), paginado."""
    return render(
        request, "content/text_archive.html", {"articles": _paginate(request, _published())}
    )


def article_detail(request, slug):
    article, preview = publishing.piece_for(
        request,
        Article.objects.select_related("section", "cover_image").prefetch_related(
            Article.bylines_prefetch(),
            Prefetch(
                "reviewed_works", queryset=Work.objects.select_related("publisher", "cover_image")
            ),
            "tags",
        ),
        slug=slug,
    )
    pie = [puerta("Índice", "Todos los textos", reverse("content:text_archive"))]
    if article.section:
        pie.append(puerta("Sección", article.section.name, article.section.get_absolute_url()))
    pie += firmas(article.bylines)
    anterior, siguiente = vecinos(Article.objects.published(), article)
    pie += puertas_vecinas(anterior, siguiente, "Texto", lambda a: a.title)
    response = render(
        request,
        "content/article_detail.html",
        {"article": article, "pie": pie, "preview": preview},
    )
    return publishing.marked_as_preview(response, preview)


def section_detail(request, slug):
    section = get_object_or_404(Section, slug=slug)
    return render(
        request,
        "content/section_detail.html",
        {"section": section, "articles": _paginate(request, _published().filter(section=section))},
    )


def tag_detail(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    return render(
        request,
        "content/tag_detail.html",
        {"tag": tag, "articles": _paginate(request, _published().filter(tags=tag))},
    )


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
            "poems": _published_poems().filter(authors=contributor),
            "articles": _paginate(request, _published().filter(authors=contributor)),
        },
    )


def collection_index(request):
    collections = Collection.objects.published()
    return render(request, "content/collection_index.html", {"collections": collections})


def poem_index(request):
    return render(
        request, "content/poem_index.html", {"poems": _paginate(request, _published_poems())}
    )


def poem_detail(request, slug):
    poem, preview = publishing.piece_for(
        request,
        Poem.objects.select_related("recording").prefetch_related(Poem.bylines_prefetch()),
        slug=slug,
    )
    anterior, siguiente = vecinos(Poem.objects.published(), poem)
    colecciones = Collection.objects.published().filter(poems=poem).order_by("title")
    pie = [puerta("Índice", "Todos los poemas", reverse("content:poem_index"))]
    pie += firmas(poem.bylines)
    pie += [puerta("En la colección", c.title, c.get_absolute_url()) for c in colecciones]
    pie += puertas_vecinas(anterior, siguiente, "Poema", lambda p: p.title)
    response = render(
        request, "content/poem_detail.html", {"poem": poem, "pie": pie, "preview": preview}
    )
    return publishing.marked_as_preview(response, preview)


def collection_detail(request, slug):
    collection, preview = publishing.piece_for(request, Collection.objects.all(), slug=slug)
    # Secuencia curada única: artículos y poemas publicados, mezclados por `position`.
    article_links = (
        CollectionArticle.objects.filter(
            collection=collection, article__in=Article.objects.published()
        )
        .select_related("article", "article__section")
        .prefetch_related(Article.bylines_prefetch("article__"))
    )
    poem_links = CollectionPoem.objects.filter(
        collection=collection, poem__in=Poem.objects.published()
    ).prefetch_related(Poem.bylines_prefetch("poem__"))
    entries = [("article", link.position, link.article) for link in article_links]
    entries += [("poem", link.position, link.poem) for link in poem_links]
    items = [{"kind": kind, "object": obj} for kind, _, obj in sorted(entries, key=lambda e: e[1])]
    response = render(
        request,
        "content/collection_detail.html",
        {"collection": collection, "items": items, "preview": preview},
    )
    return publishing.marked_as_preview(response, preview)


def page_detail(request, slug):
    page, preview = publishing.piece_for(request, Page.objects.all(), slug=slug)
    response = render(request, "content/page_detail.html", {"page": page, "preview": preview})
    return publishing.marked_as_preview(response, preview)
