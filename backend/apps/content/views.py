import logging
import unicodedata

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import F, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_safe
from django_ratelimit.decorators import ratelimit

from apps.agenda.models import Event, EventPhoto
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.reviews.models import Work
from apps.showcase.models import Publication, SiteProfile
from apps.submissions.models import Call
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
from .pie import firmas, puerta, puertas_vecinas, vecinos
from .services import coincidencias_por_nombre, ultima_publicacion
from .templatetags.versos import primeros_versos

logger = logging.getLogger(__name__)


def _published():
    # cover_image: la fila de cada texto enseña su imagen en miniatura.
    return (
        Article.objects.published()
        .select_related("section", "cover_image")
        .prefetch_related("authors")
    )


def _published_poems():
    # select_related("recording"): `published_recording` lo consulta en las fichas y en
    # las tarjetas de los listados; sin esto sería una consulta por poema.
    return Poem.objects.published().select_related("recording").prefetch_related("authors")


def _paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


# «Las voces» en la portada (D23): cinco retratos a la vez, en una fila; en el teléfono, tres.
# Las demás vienen en la página, escondidas, y el relevo las trae de a una.
A_LA_VISTA = 5
A_LA_VISTA_TELEFONO = 3

# El estante de la portada (D24, más largo en D25): una publicación de frente y hasta siete de
# lomo, lo que cabe a 951 px junto a la ficha. Al frente va la marcada «Featured» en el panel y,
# si no hay, la primera según su orden («Position»).
ESTANTE = 8


# La tirada de la portada (D19): como mucho cinco registros. Las buenas prácticas de
# carruseles piden de 2 a 5, para llegar al último en pocos pasos.
TOPE_TIRADA = 5
NUMERALES = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco"}
# Un título más largo se compone un paso más chico, para que no pase de dos líneas.
TITULO_LARGO = 34


def _registros_destacados(profile):
    """Los pliegos de la tirada de la portada (D19): los registros publicados que el colectivo
    marcó como destacados, en su orden. Sin ninguno marcado, hace de respaldo el registro
    destacado del perfil del sitio, que era lo que se elegía antes. Cada pliego lleva su
    imagen (el póster o, si no tiene, la primera foto del evento: nunca nada con el título
    impreso, que ya va en grande), el primer verso del poema que se lee, quién lee, dónde
    y cuándo."""
    consulta = (
        Recording.objects.published()
        .select_related("poster", "event")
        .prefetch_related(
            "participants",
            # Solo las fotos de eventos publicados: las de uno oculto nunca llegan al pliego.
            Prefetch(
                "event__photos",
                queryset=EventPhoto.objects.filter(
                    event__in=Event.objects.published()
                ).select_related("asset"),
            ),
        )
    )
    registros = list(consulta.filter(featured=True)[:TOPE_TIRADA])
    if not registros and profile.featured_recording_id:
        registros = list(consulta.filter(pk=profile.featured_recording_id))
    if not registros:
        return []
    # El poema que se lee en cada registro: el último publicado que lo enlaza.
    poemas = {}
    for poema in (
        Poem.objects.published()
        .filter(recording__in=registros)
        .prefetch_related("authors")
        .order_by("-published_at")
    ):
        poemas.setdefault(poema.recording_id, poema)
    pliegos = []
    for registro in registros:
        evento = registro.public_event
        fotos = list(evento.photos.all()) if evento else []
        poema = poemas.get(registro.pk)
        autores = ", ".join(c.display_name for c in poema.authors.all()) if poema else ""
        if evento and evento.starts_at:
            cuando = registro.recorded_on or timezone.localtime(evento.starts_at).date()
        else:
            cuando = registro.recorded_on
        pliegos.append(
            {
                "titulo": registro.title,
                "url": registro.get_absolute_url(),
                "tipo": registro.get_kind_display(),
                "duracion": registro.duracion,
                "audio": registro.kind == Recording.Kind.AUDIO,
                "imagen": registro.poster or (fotos[0].asset if fotos else None),
                "verso": (primeros_versos(poema.body, 1) or [""])[0] if poema else "",
                "firma": ", ".join(p for p in (autores, f"«{poema.title}»") if p) if poema else "",
                "voces": [c.display_name for c in registro.participants.all()],
                "lugar": ", ".join(p for p in (evento.venue_name, evento.city) if p)
                if evento
                else "",
                "ciudad": evento.city if evento else "",
                "fecha": cuando,
                "largo": len(registro.title) > TITULO_LARGO,
            }
        )
    return pliegos


def home(request):
    # Con el poema destacado y la obra de la portada en la misma consulta. Los registros de
    # la tirada se piden aparte, con lo que cada pliego enseña.
    profile = SiteProfile.load("featured_poem", "hero_image", "hero_image_phone")
    featured_poem = profile.featured_poem
    if featured_poem and not featured_poem.is_published:
        featured_poem = None  # el destacado solo se muestra si está publicado
    # La tirada de registros (D19). Sin ningún registro, el poema destacado, como antes:
    # nunca los dos a la vez.
    registros = _registros_destacados(profile)
    featured = (
        {"kind": "poem", "object": featured_poem} if featured_poem and not registros else None
    )
    # Todas, sin tope: a cada una le llega su turno en el relevo. Las escondidas solo cuestan
    # su marcado; sus retratos se piden cuando les toca. Se materializa para contarlas.
    _members = list(Contributor.objects.members())
    integrantes = len(_members)
    # Las destacadas primero: la primera del estante es la que va de frente. Con su editorial:
    # la ficha la nombra, y sin esto era una consulta por publicación.
    publicaciones = list(
        Publication.objects.published()
        .select_related("cover", "publisher")
        .order_by("-featured", "position", "-year", "title")[:ESTANTE]
    )
    proximo = Event.objects.upcoming().first()
    # La cejilla del titular: el lema, el lugar, el año y cuántas son. El Instagram lo
    # añade la plantilla, con las redes que ya trae el procesador del perfil.
    cejilla = profile.presentacion
    if integrantes:
        cejilla.append(f"{integrantes} integrante{'s' if integrantes != 1 else ''}")
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
            "integrantes_vista": _members[:A_LA_VISTA],
            "integrantes_resto": _members[A_LA_VISTA:],
            # En el teléfono se ven tres: con cuatro o más ya hay a quién traer deslizando.
            "relevo_integrantes": len(_members) > A_LA_VISTA_TELEFONO,
            "featured": featured,
            "registros": registros,
            "registros_cuantos": NUMERALES.get(len(registros), str(len(registros))),
            "next_event": proximo,
            "publications": publicaciones,
            # El sello del titular: solo mientras haya una convocatoria abierta.
            "convocatoria": Call.objects.open_now().first(),
            "integrantes": integrantes,
            "puertas": puertas,
            "cejilla": cejilla,
            # La obra de la primera vista (D18). Sin ella, la plantilla pone la lámina.
            "portada_imagen": profile.hero_image,
            "portada_telefono": profile.hero_image_phone,
            # El cierre para programadores y jurados: lo último que hicieron y cuándo
            # publicaron por última vez.
            "ultima_actividad": Event.objects.past().first(),
            "ultima_publicacion": ultima_publicacion(),
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
    article, preview = publishing.piece_for(
        request,
        Article.objects.select_related("section", "cover_image").prefetch_related(
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
        return redirect("people:member_detail", slug=slug)
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
        Poem.objects.select_related("recording").prefetch_related(_firmas_con_retrato()),
        slug=slug,
    )
    anterior, siguiente = vecinos(Poem.objects.published(), poem)
    colecciones = Collection.objects.published().filter(poems=poem).order_by("title")
    pie = [puerta("Índice", "Todos los poemas", reverse("content:poem_index"))]
    pie += firmas(poem.authors.all())
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
        .prefetch_related("article__authors")
    )
    poem_links = CollectionPoem.objects.filter(
        collection=collection, poem__in=Poem.objects.published()
    ).prefetch_related("poem__authors")
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


def _strip_accents(text):
    """Quita los diacríticos (á→a, ñ→n, …) para que la búsqueda sea insensible a
    acentos: el search_vector se construye con unaccent() en el trigger, así que el
    término debe ir igual de despojado para que ambos lados coincidan."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


# Tope de resultados de cada grupo, y de candidatos que se traen de cada tabla: diez en la
# página de búsqueda y cinco en el panel de la lupa, que es un adelanto (lleva a la página).
SEARCH_RESULTS = 10
SEARCH_RESULTS_PANEL = 5
# Longitud máxima de la consulta: por encima de esto no aporta precisión y solo
# encarece el `to_tsquery`.
SEARCH_MAX_QUERY = 120
# Los grupos de resultados (ticket 5.4), en el orden en que se enseñan: quien busca un
# nombre lo encuentra arriba; después, la obra en el orden de la barra, y las actividades.
GRUPOS_DE_BUSQUEDA = (
    ("persona", "Personas"),
    ("poema", "Poemas"),
    ("texto", "Textos"),
    ("registro", "Registros"),
    ("publicacion", "Publicaciones"),
    ("actividad", "Actividades"),
)


def _dato(*partes):
    """«Video · 2026», «Recital · 28 Abr 2026 · Santiago»: lo que haya, con puntos medios."""
    return " · ".join(str(parte) for parte in partes if parte)


def _resultado_por_nombre(fila):
    """Una fila de `coincidencias_por_nombre`: adónde lleva y qué la acompaña."""
    tipo, slug, dato = fila["tipo"], fila["slug"], fila["dato"]
    if tipo == "persona":
        if fila["integrante"]:
            return reverse("people:member_detail", args=[slug]), dato or "Integrante"
        return reverse("content:contributor_detail", args=[slug]), "Colaborador"
    if tipo == "registro":
        clase = dict(Recording.Kind.choices).get(dato, dato)
        return reverse("media:recording_detail", args=[slug]), _dato(clase, fila["anio"])
    if tipo == "publicacion":
        clase = dict(Publication.Kind.choices).get(dato, dato)
        return reverse("showcase:publication_detail", args=[slug]), _dato(clase, fila["anio"])
    clase = dict(Event.Type.choices).get(dato, dato)
    cuando = date_format(timezone.localtime(fila["fecha"]), "j M Y")
    return reverse("agenda:event_detail", args=[slug]), _dato(clase, cuando, fila["lugar"])


# HEAD ejecuta la vista entera (Django solo descarta el cuerpo): cuenta para el límite como
# un GET. Los demás métodos no tienen nada que hacer aquí.
@require_safe
@ratelimit(key="ip", rate="60/m", method=["GET", "HEAD"], block=False)
def search(request):
    """Buscador en vivo (htmx) y página de búsqueda: textos y poemas publicados (FTS) y,
    por nombre o título, personas, registros, publicaciones y actividades (ticket 5.4).

    Endurecido tras el hallazgo S-04: era el endpoint público más caro del sitio y el
    único sin ningún control anti-abuso. Además, el recorte a 10 se hacía en Python
    DESPUÉS de materializar todas las filas que casaban —con el cuerpo entero de cada
    artículo—, así que el SQL salía sin LIMIT y el coste crecía con el archivo.

    El rate (60/m) deja holgura al buscador en vivo, que dispara una petición por
    pulsación con 300 ms de rebote, y acota el abuso sostenido.

    Los resultados van por grupos, cada uno con su tope. Son tres consultas, sea cual sea
    el tamaño del archivo: textos, poemas y una que une los otros cuatro tipos. Los textos
    y los poemas ya no precargan sus autores, que los resultados no enseñan: eran dos
    consultas más por búsqueda.
    """
    # El byte NUL no lo admite un campo de texto de PostgreSQL: llegaba hasta el driver
    # y producía un DataError no capturado, es decir un 500 público con `?q=%00`.
    q = request.GET.get("q", "").replace("\x00", "")[:SEARCH_MAX_QUERY].strip()
    # htmx pide solo el fragmento (overlay en vivo); una navegación normal (sin JS)
    # recibe la página completa con layout, para que la búsqueda degrade con gracia.
    panel = bool(request.headers.get("HX-Request"))
    tope = SEARCH_RESULTS_PANEL if panel else SEARCH_RESULTS
    grupos = []
    limited = bool(getattr(request, "limited", False))
    if q and not limited:
        termino = _strip_accents(q)
        query = SearchQuery(termino, config="spanish")
        # `[:tope]` en cada queryset hace que el LIMIT viaje al SQL, y `only()` evita
        # traer el texto completo de cada pieza para nada.
        articles = (
            Article.objects.published()
            .filter(search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .only("slug", "title", "type")
            .order_by("-rank")[:tope]
        )
        poems = (
            Poem.objects.published()
            .filter(search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .only("slug", "title")
            .order_by("-rank")[:tope]
        )
        por_tipo = {tipo: [] for tipo, _ in GRUPOS_DE_BUSQUEDA}
        try:
            por_tipo["texto"] = [
                {
                    "url": reverse("content:article_detail", args=[a.slug]),
                    "title": a.title,
                    "dato": a.get_type_display(),
                }
                for a in articles
            ]
            por_tipo["poema"] = [
                {"url": p.get_absolute_url(), "title": p.title, "dato": ""} for p in poems
            ]
            # Una letra sola casa con casi todos los nombres: no dice nada.
            if len(termino) >= 2:
                for fila in coincidencias_por_nombre(termino, tope):
                    url, dato = _resultado_por_nombre(fila)
                    por_tipo[fila["tipo"]].append(
                        {"url": url, "title": fila["titulo"], "dato": dato}
                    )
        except DatabaseError:
            # Red de seguridad: cualquier término que el motor de FTS rechace devuelve
            # «sin resultados» en vez de un 500 público.
            logger.warning("Consulta de búsqueda rechazada por la BD", exc_info=True)
            por_tipo = {}
        grupos = [
            {"titulo": titulo, "resultados": por_tipo[tipo]}
            for tipo, titulo in GRUPOS_DE_BUSQUEDA
            if por_tipo.get(tipo)
        ]
    template = "content/partials/_search_results.html" if panel else "content/search.html"
    return render(request, template, {"grupos": grupos, "q": q, "limited": limited, "panel": panel})


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
