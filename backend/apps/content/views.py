from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.agenda.models import Event
from apps.agenda.services import stats as trajectory_stats
from apps.people.models import Contributor
from apps.showcase.models import Partner, PressMention, Publication, SiteProfile

from .models import (
    Article,
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialStatus,
    Page,
    Poem,
    PublishStatus,
    Section,
    Tag,
)


def _published():
    return (
        Article.objects.filter(status=EditorialStatus.PUBLISHED)
        .select_related("section")
        .prefetch_related("authors")
    )


def _published_poems():
    return Poem.objects.filter(status=EditorialStatus.PUBLISHED).prefetch_related("authors")


def _paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def home(request):
    profile = SiteProfile.load()  # garantiza la fila singleton (nunca None)
    featured_poem = profile.featured_poem
    if featured_poem and featured_poem.status != EditorialStatus.PUBLISHED:
        featured_poem = None  # el destacado solo se muestra si está publicado
    featured_recording = profile.featured_recording
    if featured_recording and not featured_recording.published:
        featured_recording = None
    # Un solo destacado grande (evita apilar dos): el registro manda sobre el poema.
    featured = None
    if featured_recording:
        featured = {"kind": "recording", "object": featured_recording}
    elif featured_poem:
        featured = {"kind": "poem", "object": featured_poem}
    return render(
        request,
        "content/home.html",
        {
            "articles": _published()[:5],  # portada curada; el archivo vive en /textos/
            "members": Contributor.members()[:8],
            "featured": featured,
            "next_event": Event.upcoming().first(),
            "stats": trajectory_stats(),
            "publications": Publication.objects.filter(published=True).select_related("cover")[:4],
            "press_quotes": PressMention.objects.filter(published=True).exclude(quote="")[:2],
            "partners": Partner.objects.filter(active=True)[:6],
        },
    )


def text_archive(request):
    """Archivo completo de textos (reseñas, ensayos, entrevistas), paginado."""
    return render(
        request, "content/text_archive.html", {"articles": _paginate(request, _published())}
    )


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
    if contributor.is_member:
        # URL canónica única por persona: el integrante vive en su perfil rico.
        return redirect("people:member_detail", slug=slug)
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


def poem_index(request):
    return render(
        request, "content/poem_index.html", {"poems": _paginate(request, _published_poems())}
    )


def poem_detail(request, slug):
    poem = get_object_or_404(_published_poems().select_related("recording"), slug=slug)
    return render(request, "content/poem_detail.html", {"poem": poem})


def collection_detail(request, slug):
    collection = get_object_or_404(Collection, slug=slug, status=PublishStatus.PUBLISHED)
    # Secuencia curada única: artículos y poemas publicados, mezclados por `position`.
    article_links = (
        CollectionArticle.objects.filter(
            collection=collection, article__status=EditorialStatus.PUBLISHED
        )
        .select_related("article", "article__section")
        .prefetch_related("article__authors")
    )
    poem_links = CollectionPoem.objects.filter(
        collection=collection, poem__status=EditorialStatus.PUBLISHED
    ).prefetch_related("poem__authors")
    entries = [("article", link.position, link.article) for link in article_links]
    entries += [("poem", link.position, link.poem) for link in poem_links]
    items = [{"kind": kind, "object": obj} for kind, _, obj in sorted(entries, key=lambda e: e[1])]
    return render(
        request,
        "content/collection_detail.html",
        {"collection": collection, "items": items},
    )


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, status=PublishStatus.PUBLISHED)
    return render(request, "content/page_detail.html", {"page": page})


def search(request):
    """Buscador en vivo (htmx): busca en artículos y poemas publicados (FTS)."""
    q = request.GET.get("q", "").strip()
    results = []
    if q:
        query = SearchQuery(q, config="spanish")
        articles = (
            _published()
            .filter(search_vector=query)
            .annotate(rank=SearchRank("search_vector", query))
        )
        poems = (
            _published_poems()
            .filter(search_vector=query)
            .annotate(rank=SearchRank("search_vector", query))
        )
        items = [
            {
                "url": reverse("content:article_detail", args=[a.slug]),
                "title": a.title,
                "kind": a.get_type_display(),
                "rank": a.rank,
            }
            for a in articles
        ] + [
            {
                "url": p.get_absolute_url(),
                "title": p.title,
                "kind": "Poema",
                "rank": p.rank,
            }
            for p in poems
        ]
        results = sorted(items, key=lambda r: r["rank"], reverse=True)[:10]
    return render(
        request,
        "content/partials/_search_results.html",
        {"results": results, "q": q},
    )


def healthz(request):
    """Liveness: sonda barata para el healthcheck del contenedor y el proxy (no toca la BD)."""
    return HttpResponse("ok", content_type="text/plain")


def _db_ok():
    """La BD responde a una consulta trivial."""
    from django.db import connections

    try:
        with connections["default"].cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        return False


def _broker_ok():
    """El broker de Celery (Redis) acepta un PING."""
    import redis
    from django.conf import settings

    try:
        client = redis.from_url(
            settings.CELERY_BROKER_URL, socket_connect_timeout=3, socket_timeout=3
        )
        return bool(client.ping())
    except Exception:
        return False


def readyz(request):
    """Readiness: verifica dependencias (BD + broker). 200 si listo, 503 si no.

    Distinto de healthz (liveness): apto para monitoreo externo de uptime y para
    detectar que la app no puede operar aunque el proceso siga vivo.
    """
    import json

    checks = {"database": _db_ok(), "broker": _broker_ok()}
    ready = all(checks.values())
    return HttpResponse(
        json.dumps({"status": "ready" if ready else "not-ready", "checks": checks}),
        content_type="application/json",
        status=200 if ready else 503,
    )


def robots(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
