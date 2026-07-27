from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.people.models import Contributor

from .models import (
    Article,
    ArticleStatus,
    Collection,
    CollectionArticle,
    Page,
    PublishStatus,
    Section,
    Tag,
)


def _published():
    return (
        Article.objects.filter(status=ArticleStatus.PUBLISHED)
        .select_related("section")
        .prefetch_related("authors")
    )


def _paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def home(request):
    return render(request, "content/home.html", {"articles": _paginate(request, _published())})


def article_detail(request, slug):
    article = get_object_or_404(_published(), slug=slug)
    return render(request, "content/article_detail.html", {"article": article})


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
    contributor = get_object_or_404(Contributor, slug=slug)
    return render(
        request,
        "content/contributor_detail.html",
        {
            "contributor": contributor,
            "articles": _paginate(request, _published().filter(authors=contributor)),
        },
    )


def collection_index(request):
    collections = Collection.objects.filter(status=PublishStatus.PUBLISHED)
    return render(request, "content/collection_index.html", {"collections": collections})


def collection_detail(request, slug):
    collection = get_object_or_404(Collection, slug=slug, status=PublishStatus.PUBLISHED)
    # Orden curado (CollectionArticle.position), solo artículos publicados.
    links = (
        CollectionArticle.objects.filter(
            collection=collection, article__status=ArticleStatus.PUBLISHED
        )
        .select_related("article", "article__section")
        .prefetch_related("article__authors")
        .order_by("position")
    )
    articles = [link.article for link in links]
    return render(
        request,
        "content/collection_detail.html",
        {"collection": collection, "articles": articles},
    )


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, status=PublishStatus.PUBLISHED)
    return render(request, "content/page_detail.html", {"page": page})


def search(request):
    """Buscador en vivo (htmx): devuelve solo el fragmento de resultados."""
    q = request.GET.get("q", "").strip()
    results = []
    if q:
        query = SearchQuery(q, config="spanish")
        results = (
            _published()
            .filter(search_vector=query)
            .annotate(rank=SearchRank("search_vector", query))
            .order_by("-rank")[:10]
        )
    return render(
        request,
        "content/partials/_search_results.html",
        {"results": results, "q": q},
    )


def healthz(request):
    """Sonda de salud para el healthcheck del contenedor y el proxy (sin tocar la BD)."""
    return HttpResponse("ok", content_type="text/plain")


def robots(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
