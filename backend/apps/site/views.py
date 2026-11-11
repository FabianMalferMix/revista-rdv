import logging

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import OperationalError, transaction
from django.db.models import F
from django.shortcuts import render
from django.views.decorators.http import require_safe
from django.views.decorators.vary import vary_on_headers

from apps.agenda.models import Event, url_for_event
from apps.content.models import SEARCH_CONFIG, Article, Poem
from apps.media.models import Recording, url_for_recording
from apps.people.models import url_for_person
from apps.showcase.models import Publication, SiteProfile, url_for_publication
from config.ratelimit import rate_limited

from . import portada
from .services import (
    EVENT,
    PERSON,
    POEM,
    PUBLICATION,
    RECORDING,
    SEARCH_TYPES,
    TEXT,
    coincidencias_por_nombre,
)

logger = logging.getLogger(__name__)


@require_safe
def home(request):
    """La portada: junta sus bloques, cada uno desde su constructor (`portada.py`)."""
    # Con el poema destacado y la obra de la primera vista en la misma consulta.
    profile = SiteProfile.load("featured_poem", "hero_image", "hero_image_phone")
    tirada = portada.build_tirada(profile)
    voces = portada.build_voces()
    return render(
        request,
        "site/home.html",
        {
            "arte": portada.build_arte(profile),
            "hoja": portada.build_hoja(profile, len(voces.members)),
            "tirada": tirada,
            "featured_poem": portada.featured_poem(profile, tirada),
            "next_event": portada.next_event(),
            "obra": portada.build_obra(),
            "voces": voces,
            "publications": portada.build_estante(),
            "cierre": portada.build_cierre(),
        },
    )


# Tope de resultados de cada grupo, y de candidatos que se traen de cada tabla: diez en la
# página de búsqueda y cinco en el panel de la lupa, que es un adelanto (lleva a la página).
SEARCH_RESULTS = 10
SEARCH_RESULTS_PANEL = 5
# Longitud máxima de la consulta: por encima de esto no aporta precisión y solo
# encarece el `to_tsquery`.
SEARCH_MAX_QUERY = 120
TOO_MANY_SEARCHES = "Demasiadas búsquedas seguidas. Espera un momento e inténtalo de nuevo."
# El id del panel de la lupa (base.html), que htmx manda en HX-Target al pedir sus resultados.
SEARCH_PANEL = "search-results"


# Cada resultado lleva su dirección, su título y los datos que lo distinguen, que la plantilla
# escribe al lado (`site/partials/_search_results.html`): de una persona, si es integrante y su
# rol; de lo demás, su clase (`kind`, el rótulo del tipo en el modelo) y, si los tiene, la fecha
# o el año y el lugar.


def _person(fila):
    return {
        "url": url_for_person(fila["slug"], fila["integrante"]),
        "person": True,
        "member": fila["integrante"],
        "role": fila["dato"],
    }


def _recording(fila):
    return {
        "url": url_for_recording(fila["slug"]),
        "kind": dict(Recording.Kind.choices).get(fila["dato"], fila["dato"]),
        "year": fila["anio"],
    }


def _publication(fila):
    return {
        "url": url_for_publication(fila["slug"]),
        "kind": dict(Publication.Kind.choices).get(fila["dato"], fila["dato"]),
        "year": fila["anio"],
    }


def _event(fila):
    return {
        "url": url_for_event(fila["slug"]),
        "kind": dict(Event.Type.choices).get(fila["dato"], fila["dato"]),
        "date": fila["fecha"],
        "place": fila["lugar"],
    }


# Adónde lleva cada tipo de coincidencia por nombre y qué la acompaña.
_NAME_RESULTS = {PERSON: _person, RECORDING: _recording, PUBLICATION: _publication, EVENT: _event}


def _resultado_por_nombre(fila):
    """Una fila de `coincidencias_por_nombre`, como resultado. Un tipo que no está en la tabla
    es un error de programación, no una actividad."""
    try:
        describe = _NAME_RESULTS[fila["tipo"]]
    except KeyError:
        raise ValueError(f"Tipo de búsqueda desconocido: {fila['tipo']!r}") from None
    return {"title": fila["titulo"], **describe(fila)}


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


def _search_query(request):
    # PostgreSQL no admite el byte nulo en un campo de texto: sin quitarlo, `?q=%00` llegaría
    # al driver y la página respondería 500.
    return _trim_search_query(request.GET.get("q", "").replace("\x00", ""))


def _wants_panel(request):
    """La lupa pide el fragmento de sus resultados: htmx manda HX-Request y, en HX-Target, el id
    del panel. Cualquier otra petición, también una de htmx con otro destino, recibe la página
    completa, que es la búsqueda sin JavaScript."""
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Target") == SEARCH_PANEL
    )


def _search_response(request, q, grupos, aviso):
    """El fragmento del panel o la página de búsqueda, según quién la pida. `aviso` dice por qué
    no se buscó, si no se buscó."""
    panel = _wants_panel(request)
    return render(
        request,
        "site/partials/_search_results.html" if panel else "site/search.html",
        {
            "grupos": grupos,
            "total": sum(len(grupo["resultados"]) for grupo in grupos),
            "q": q,
            "aviso": aviso,
            "panel": panel,
        },
    )


def _search_limited(request, aviso):
    """Pasado el límite de tasa, la misma página, sin buscar, con el aviso."""
    return _search_response(request, _search_query(request), [], aviso)


# HEAD ejecuta la vista entera (Django solo descarta el cuerpo): cuenta para el límite como
# un GET. Los demás métodos no tienen nada que hacer aquí. El fragmento y la página comparten
# la URL: la respuesta declara de qué cabeceras depende, para que ninguna caché las confunda.
@require_safe
@vary_on_headers("HX-Request", "HX-Target")
@rate_limited("60/m", notice=TOO_MANY_SEARCHES, limited=_search_limited)
def search(request):
    """El buscador en vivo (htmx) y la página de búsqueda: los textos y los poemas publicados,
    por su texto completo, y por nombre o título, las personas, los registros, las
    publicaciones y las actividades.

    Es la vista pública más cara del sitio: lleva un límite de tasa, y el tope de cada grupo
    viaja al SQL, así que el coste no crece con el archivo. El límite (60/m) deja holgura al
    buscador en vivo, que dispara una petición por pulsación con 300 ms de rebote, y acota el
    abuso sostenido.

    Los resultados van por grupos, cada uno con su tope. Son tres consultas, sea cual sea
    el tamaño del archivo: textos, poemas y una que une los otros cuatro tipos. Los textos
    y los poemas no precargan sus autores, que los resultados no enseñan.
    """
    q = _search_query(request)
    tope = SEARCH_RESULTS_PANEL if _wants_panel(request) else SEARCH_RESULTS
    grupos = []
    if q:
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
            # Las tres consultas, en un bloque atómico: PostgreSQL aborta la transacción en que
            # falla una consulta, y el punto de guardado del bloque deja intacta la de fuera, si
            # la hay (ATOMIC_REQUESTS), para que la página pueda seguir consultando la base.
            with transaction.atomic():
                por_tipo[TEXT] = [
                    {"url": a.get_absolute_url(), "title": a.title, "kind": a.get_type_display()}
                    for a in articles
                ]
                por_tipo[POEM] = [{"url": p.get_absolute_url(), "title": p.title} for p in poems]
                # Una letra sola casa con casi todos los nombres: no dice nada.
                if len(q) >= 2:
                    for fila in coincidencias_por_nombre(q, tope):
                        resultado = _resultado_por_nombre(fila)
                        por_tipo[fila["tipo"]].append(resultado)
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
    return _search_response(request, q, grupos, "")
