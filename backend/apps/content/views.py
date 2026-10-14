import logging
import unicodedata

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django_ratelimit.decorators import ratelimit

from apps.agenda.models import Event
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.reviews.models import Work
from apps.showcase.models import Publication, SiteProfile
from apps.submissions.models import Call

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
from .pie import firmas, puerta, puertas_vecinas, vecinos

logger = logging.getLogger(__name__)


def _published():
    # cover_image: la fila de cada texto enseña su imagen en miniatura.
    return (
        Article.objects.filter(status=EditorialStatus.PUBLISHED)
        .select_related("section", "cover_image")
        .prefetch_related("authors")
    )


def _published_poems():
    # select_related("recording"): `published_recording` lo consulta en las fichas y en
    # las tarjetas de los listados; sin esto sería una consulta por poema.
    return (
        Poem.objects.filter(status=EditorialStatus.PUBLISHED)
        .select_related("recording")
        .prefetch_related("authors")
    )


def _paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


# Por debajo de este número, la rejilla ya enseña a todo el mundo a la vez y una
# cinta enseñaría MENOS, no más. Por encima no caben y la cinta gana.
UMBRAL_CINTA = 12
# Tope de la cinta: con 16 la vuelta completa dura 96s; a partir de ahí el enlace
# «Conoce al colectivo» se hace cargo del resto.
TOPE_CINTA = 16


def _objeto_del_titular(publicaciones, proximo):
    """El objeto real que acompaña al nombre en el titular de la portada (ticket 4.2): la
    primera cubierta del catálogo o, si no hay, el afiche de la próxima actividad. No el
    póster del registro destacado, que se ve justo debajo, ni la imagen para compartir,
    que lleva el nombre escrito y lo repetiría. Sin objeto, el titular va a todo el ancho.
    Sale de lo que la portada ya trae: no añade consultas."""
    for pub in publicaciones:
        if pub.cover:
            return {
                "publicacion": pub,
                "imagen": pub.cover,
                "url": pub.get_absolute_url(),
                "rotulo": pub.get_kind_display(),
                "titulo": pub.title,
                "dato": pub.year or "",
            }
    if proximo and proximo.poster:
        return {
            "imagen": proximo.poster,
            "url": proximo.get_absolute_url(),
            "rotulo": "Próxima actividad",
            "titulo": proximo.title,
            "dato": date_format(timezone.localtime(proximo.starts_at), "j \\d\\e F"),
        }
    return None


def _ultima_publicacion():
    """Cuándo publicó el colectivo por última vez: un poema, un texto o un registro. Es el
    «Actualizado el…» del cierre de la portada, en una sola consulta. Cuenta la fecha de
    publicación y no la de edición: corregir una errata no hace más reciente la portada."""
    fechas = (
        Article.objects.filter(status=EditorialStatus.PUBLISHED, published_at__isnull=False)
        .order_by()
        .values_list("published_at", flat=True)
        .union(
            Poem.objects.filter(status=EditorialStatus.PUBLISHED, published_at__isnull=False)
            .order_by()
            .values_list("published_at", flat=True),
            Recording.objects.filter(published=True, published_at__isnull=False)
            .order_by()
            .values_list("published_at", flat=True),
        )
        .order_by("-published_at")
    )
    return next(iter(fechas[:1]), None)


def home(request):
    # Con el registro y el poema destacados, y el evento y el póster del registro, en la
    # misma consulta: eran cuatro consultas sueltas.
    profile = SiteProfile.load(
        "featured_recording__event", "featured_recording__poster", "featured_poem"
    )
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
    # Se materializa para poder contar sin una segunda consulta.
    _members = list(Contributor.members()[:TOPE_CINTA])
    # Cuántas integrantes hay: la cinta ya las trajo, salvo que lleguen a su tope.
    integrantes = len(_members) if len(_members) < TOPE_CINTA else Contributor.members().count()
    # Con su editorial: la tarjeta la nombra, y sin esto era una consulta por publicación.
    publicaciones = list(
        Publication.objects.filter(published=True).select_related("cover", "publisher")[:4]
    )
    proximo = Event.upcoming().first()
    # La cejilla del titular: el lema, el lugar, el año y cuántas son. El Instagram lo
    # añade la plantilla, con las redes que ya trae el procesador del perfil.
    cejilla = [
        parte
        for parte in (
            profile.tagline,
            profile.location,
            f"desde {profile.founded_year}" if profile.founded_year else "",
            f"{integrantes} integrante{'s' if integrantes != 1 else ''}" if integrantes else "",
        )
        if parte
    ]
    objeto = _objeto_del_titular(publicaciones, proximo)
    # El cierre para programadores y jurados: puertas a lo que piden (D9), como las salidas
    # al pie de una ficha. La cita y los aliados ya están en el titular.
    puertas = [
        puerta("Kit de prensa", "Dossier", reverse("showcase:dossier")),
        puerta("Notas y entrevistas", "Prensa", reverse("showcase:press_index")),
        puerta("Quiénes nos apoyan", "Aliados", reverse("showcase:partner_index")),
    ]
    if profile.correo_de_contacto:
        puertas.append(puerta("Contacto", "Escríbenos", f"mailto:{profile.correo_de_contacto}"))
    return render(
        request,
        "content/home.html",
        {
            # La obra (ticket 4.3): los tres últimos poemas, con sus primeros versos, y los
            # tres últimos textos. El archivo de cada uno vive en su índice.
            "poemas": list(_published_poems()[:3]),
            "articles": _published()[:3],
            "members": _members,
            "cinta_integrantes": len(_members) >= UMBRAL_CINTA,
            "featured": featured,
            "next_event": proximo,
            # El bloque de publicaciones no repite el libro que ya enseña el titular.
            "publications": [
                p for p in publicaciones if p is not (objeto or {}).get("publicacion")
            ],
            # El sello del titular: solo mientras haya una convocatoria abierta.
            "convocatoria": Call.open_now().first(),
            "integrantes": integrantes,
            "titulo_integrantes": f"{integrantes} {'voz' if integrantes == 1 else 'voces'}",
            "puertas": puertas,
            "cejilla": cejilla,
            "objeto_titular": objeto,
            # El cierre para programadores y jurados: lo último que hicieron y cuándo
            # publicaron por última vez.
            "ultima_actividad": Event.past().first(),
            "ultima_publicacion": _ultima_publicacion(),
        },
    )


def text_archive(request):
    """Archivo completo de textos (reseñas, ensayos, entrevistas), paginado."""
    return render(
        request, "content/text_archive.html", {"articles": _paginate(request, _published())}
    )


def _firmas_con_retrato():
    """Las firmas con su retrato en la misma consulta: la sala de lectura lo enseña."""
    return Prefetch("authors", queryset=Contributor.objects.select_related("photo"))


def article_detail(request, slug):
    article = get_object_or_404(
        Article.objects.filter(status=EditorialStatus.PUBLISHED)
        .select_related("section", "cover_image")
        .prefetch_related(
            _firmas_con_retrato(),
            Prefetch(
                "reviewed_works", queryset=Work.objects.select_related("publisher", "cover_image")
            ),
            "tags",
        ),
        slug=slug,
    )
    pie = [puerta("Índice", "Todos los textos", reverse("content:text_archive"))]
    if article.section:
        pie.append(
            puerta(
                "Sección",
                article.section.name,
                reverse("content:section_detail", args=[article.section.slug]),
            )
        )
    pie += firmas(article.authors.all())
    anterior, siguiente = vecinos(Article.objects.filter(status=EditorialStatus.PUBLISHED), article)
    pie += puertas_vecinas(anterior, siguiente, "Texto", lambda a: a.title)
    return render(request, "content/article_detail.html", {"article": article, "pie": pie})


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
    poem = get_object_or_404(
        Poem.objects.filter(status=EditorialStatus.PUBLISHED)
        .select_related("recording")
        .prefetch_related(_firmas_con_retrato()),
        slug=slug,
    )
    anterior, siguiente = vecinos(Poem.objects.filter(status=EditorialStatus.PUBLISHED), poem)
    colecciones = Collection.objects.filter(poems=poem, status=PublishStatus.PUBLISHED).order_by(
        "title"
    )
    pie = [puerta("Índice", "Todos los poemas", reverse("content:poem_index"))]
    pie += firmas(poem.authors.all())
    pie += [puerta("En la colección", c.title, c.get_absolute_url()) for c in colecciones]
    pie += puertas_vecinas(anterior, siguiente, "Poema", lambda p: p.title)
    return render(request, "content/poem_detail.html", {"poem": poem, "pie": pie})


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


def _strip_accents(text):
    """Quita los diacríticos (á→a, ñ→n, …) para que la búsqueda sea insensible a
    acentos: el search_vector se construye con unaccent() en el trigger, así que el
    término debe ir igual de despojado para que ambos lados coincidan."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


# Tope de resultados mostrados y de candidatos que se traen de cada tabla.
SEARCH_RESULTS = 10
# Longitud máxima de la consulta: por encima de esto no aporta precisión y solo
# encarece el `to_tsquery`.
SEARCH_MAX_QUERY = 120


@ratelimit(key="ip", rate="60/m", method="GET", block=False)
def search(request):
    """Buscador en vivo (htmx): busca en artículos y poemas publicados (FTS).

    Endurecido tras el hallazgo S-04: era el endpoint público más caro del sitio y el
    único sin ningún control anti-abuso. Además, el recorte a 10 se hacía en Python
    DESPUÉS de materializar todas las filas que casaban —con el cuerpo entero de cada
    artículo—, así que el SQL salía sin LIMIT y el coste crecía con el archivo.

    El rate (60/m) deja holgura al buscador en vivo, que dispara una petición por
    pulsación con 300 ms de rebote, y acota el abuso sostenido.
    """
    # El byte NUL no lo admite un campo de texto de PostgreSQL: llegaba hasta el driver
    # y producía un DataError no capturado, es decir un 500 público con `?q=%00`.
    q = request.GET.get("q", "").replace("\x00", "")[:SEARCH_MAX_QUERY].strip()
    results = []
    limited = bool(getattr(request, "limited", False))
    if q and not limited:
        query = SearchQuery(_strip_accents(q), config="spanish")
        # `[:SEARCH_RESULTS]` en cada queryset hace que el LIMIT viaje al SQL, y
        # `defer("body")` evita traer el texto completo de cada pieza para nada.
        articles = (
            _published()
            .filter(search_vector=query)
            .annotate(rank=SearchRank("search_vector", query))
            .defer("body")
            .order_by("-rank")[:SEARCH_RESULTS]
        )
        poems = (
            _published_poems()
            .filter(search_vector=query)
            .annotate(rank=SearchRank("search_vector", query))
            .defer("body")
            .order_by("-rank")[:SEARCH_RESULTS]
        )
        try:
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
        except DatabaseError:
            # Red de seguridad: cualquier término que el motor de FTS rechace devuelve
            # «sin resultados» en vez de un 500 público.
            logger.warning("Consulta de búsqueda rechazada por la BD", exc_info=True)
            items = []
        results = sorted(items, key=lambda r: r["rank"], reverse=True)[:SEARCH_RESULTS]
    # htmx pide solo el fragmento (overlay en vivo); una navegación normal (sin JS)
    # recibe la página completa con layout, para que la búsqueda degrade con gracia.
    panel = bool(request.headers.get("HX-Request"))
    template = "content/partials/_search_results.html" if panel else "content/search.html"
    return render(
        request, template, {"results": results, "q": q, "limited": limited, "panel": panel}
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


def favicon(request):
    """Quien pide /favicon.ico (lectores de RSS, navegadores viejos, buscadores) recibe el
    icono del colectivo. Temporal: el archivo estático lleva su huella en la URL, que
    cambia con el icono, y una redirección permanente quedaría guardada para siempre."""
    return redirect(static("img/favicon.ico"))


def robots(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
