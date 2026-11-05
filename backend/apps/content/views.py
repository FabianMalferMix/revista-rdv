import logging

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.db import OperationalError
from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_safe
from django_ratelimit.decorators import ratelimit

from apps.agenda.models import Event, EventPhoto, url_for_event
from apps.media.models import TIRADA_SIZE, Recording, url_for_recording
from apps.people.models import Contributor, url_for_person
from apps.reviews.models import Work
from apps.showcase.models import Publication, SiteProfile, url_for_publication
from apps.submissions.models import Call
from config import publishing
from config.cache import SERVICE_UNAVAILABLE, counters_available

from .models import (
    SEARCH_CONFIG,
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
from .services import (
    EVENT,
    PERSON,
    POEM,
    PUBLICATION,
    RECORDING,
    SEARCH_TYPES,
    TEXT,
    coincidencias_por_nombre,
    ultima_publicacion,
)
from .templatetags.versos import primeros_versos

logger = logging.getLogger(__name__)


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


# «Las voces» en la portada (D23): cinco retratos a la vez, en una fila; en el teléfono, tres.
# Las demás vienen en la página, escondidas, y el relevo las trae de a una. Es la única fuente:
# la plantilla los pasa a integrantes.js por atributos data-, y la hoja no repite el número.
A_LA_VISTA = 5
A_LA_VISTA_TELEFONO = 3

# El estante de la portada (D24, más largo en D25): una publicación de frente y hasta siete de
# lomo, lo que cabe a 951 px junto a la ficha. Al frente va la marcada «Destacada» en el panel y,
# si no hay, la primera según su orden («Position»).
ESTANTE = 8


# La tirada de la portada (D19): como mucho TIRADA_SIZE registros, el tope que valida el panel.
TOPE_TIRADA = TIRADA_SIZE
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
        .prefetch_related(Poem.bylines_prefetch())
        .order_by("-published_at")
    ):
        poemas.setdefault(poema.recording_id, poema)
    pliegos = []
    for registro in registros:
        evento = registro.public_event
        fotos = list(evento.photos.all()) if evento else []
        poema = poemas.get(registro.pk)
        autores = ", ".join(c.display_name for c in poema.bylines) if poema else ""
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
            "a_la_vista": A_LA_VISTA,
            "a_la_vista_telefono": A_LA_VISTA_TELEFONO,
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


# Tope de resultados de cada grupo, y de candidatos que se traen de cada tabla: diez en la
# página de búsqueda y cinco en el panel de la lupa, que es un adelanto (lleva a la página).
SEARCH_RESULTS = 10
SEARCH_RESULTS_PANEL = 5
# Longitud máxima de la consulta: por encima de esto no aporta precisión y solo
# encarece el `to_tsquery`.
SEARCH_MAX_QUERY = 120
TOO_MANY_SEARCHES = "Demasiadas búsquedas seguidas. Espera un momento e inténtalo de nuevo."


def _dato(*partes):
    """«Video · 2026», «Recital · 28 Abr 2026 · Santiago»: lo que haya, con puntos medios."""
    return " · ".join(str(parte) for parte in partes if parte)


def _person(fila):
    dato = (fila["dato"] or "Integrante") if fila["integrante"] else "Colaborador"
    return url_for_person(fila["slug"], fila["integrante"]), dato


def _recording(fila):
    clase = dict(Recording.Kind.choices).get(fila["dato"], fila["dato"])
    return url_for_recording(fila["slug"]), _dato(clase, fila["anio"])


def _publication(fila):
    clase = dict(Publication.Kind.choices).get(fila["dato"], fila["dato"])
    return url_for_publication(fila["slug"]), _dato(clase, fila["anio"])


def _event(fila):
    clase = dict(Event.Type.choices).get(fila["dato"], fila["dato"])
    cuando = date_format(timezone.localtime(fila["fecha"]), "j M Y")
    return url_for_event(fila["slug"]), _dato(clase, cuando, fila["lugar"])


# Adónde lleva cada tipo de coincidencia por nombre y qué la acompaña.
_NAME_RESULTS = {PERSON: _person, RECORDING: _recording, PUBLICATION: _publication, EVENT: _event}


def _resultado_por_nombre(fila):
    """Una fila de `coincidencias_por_nombre`: adónde lleva y qué la acompaña. Un tipo que no
    está en la tabla es un error de programación, no una actividad."""
    try:
        formatter = _NAME_RESULTS[fila["tipo"]]
    except KeyError:
        raise ValueError(f"Tipo de búsqueda desconocido: {fila['tipo']!r}") from None
    return formatter(fila)


def _trim_search_query(text):
    """La consulta que se busca: sin espacios en los bordes y con SEARCH_MAX_QUERY caracteres
    como mucho. Si el tope parte una palabra, esa palabra queda fuera entera: la búsqueda exige
    todas las palabras, y un pedazo es una palabra que el texto no tiene. La palabra va de
    espacio a espacio, con su puntuación: PostgreSQL lee «Wisława-Szymborska» o «3.14» como una
    sola, y un pedazo de ellas tampoco casa. Sin ningún espacio dentro del tope no hay palabra
    entera que dejar, y la consulta se corta en el tope."""
    query = text.strip()
    if len(query) <= SEARCH_MAX_QUERY:
        return query
    head = query[:SEARCH_MAX_QUERY]
    if not head[-1].isspace() and not query[SEARCH_MAX_QUERY].isspace():
        head = head.rsplit(maxsplit=1)[0]
    return head.rstrip()


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
    q = _trim_search_query(request.GET.get("q", "").replace("\x00", ""))
    # htmx pide solo el fragmento (overlay en vivo); una navegación normal (sin JS)
    # recibe la página completa con layout, para que la búsqueda degrade con gracia.
    panel = bool(request.headers.get("HX-Request"))
    tope = SEARCH_RESULTS_PANEL if panel else SEARCH_RESULTS
    grupos = []
    limited = bool(getattr(request, "limited", False))
    # Por qué no se buscó, si no se buscó: el límite de tasa, o sus contadores caídos.
    aviso = ""
    if limited:
        aviso = TOO_MANY_SEARCHES if counters_available() else SERVICE_UNAVAILABLE
    if q and not limited:
        query = SearchQuery(q, config=SEARCH_CONFIG)
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
        por_tipo = {tipo: [] for tipo, _ in SEARCH_TYPES}
        try:
            por_tipo[TEXT] = [
                {"url": a.get_absolute_url(), "title": a.title, "dato": a.get_type_display()}
                for a in articles
            ]
            por_tipo[POEM] = [
                {"url": p.get_absolute_url(), "title": p.title, "dato": ""} for p in poems
            ]
            # Una letra sola casa con casi todos los nombres: no dice nada.
            if len(q) >= 2:
                for fila in coincidencias_por_nombre(q, tope):
                    url, dato = _resultado_por_nombre(fila)
                    por_tipo[fila["tipo"]].append(
                        {"url": url, "title": fila["titulo"], "dato": dato}
                    )
        except OperationalError:
            # Una conexión caída o una consulta cancelada por su plazo: «sin resultados» en
            # vez de un 500, y un ERROR para que llegue a Sentry. Un error de programación no
            # se captura: tiene que verse.
            logger.exception("La búsqueda no pudo consultar la base")
            por_tipo = {}
        grupos = [
            {"titulo": titulo, "resultados": por_tipo[tipo]}
            for tipo, titulo in SEARCH_TYPES
            if por_tipo.get(tipo)
        ]
    template = "content/partials/_search_results.html" if panel else "content/search.html"
    return render(
        request,
        template,
        {
            "grupos": grupos,
            "total": sum(len(grupo["resultados"]) for grupo in grupos),
            "q": q,
            "aviso": aviso,
            "panel": panel,
        },
    )
