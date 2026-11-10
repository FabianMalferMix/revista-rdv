"""Consultas que cruzan varias apps: cuándo publicó el colectivo por última vez (la portada y el
dossier), quienes participan en una ficha y las coincidencias por nombre de la búsqueda."""

from django.db.models import DateTimeField, F, IntegerField, Prefetch, Value
from django.db.models.functions import Cast, ExtractYear

from apps.agenda.models import Event
from apps.content.models import editorial_models
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.showcase.models import Publication


def ultima_publicacion():
    """Cuándo publicó el colectivo por última vez: un poema, un texto o un registro. Es el
    «Actualizado el…» del cierre de la portada y de la ficha del dossier, en una sola consulta.
    Cuenta la fecha de publicación y no la de edición: corregir una errata no hace más reciente
    la portada."""
    # Las piezas del flujo editorial, cualquiera que sea su tipo, y los registros.
    fechas = [
        model.objects.published()
        .filter(published_at__isnull=False)
        .order_by()
        .values_list("published_at", flat=True)
        for model in [*editorial_models(), Recording]
    ]
    return next(iter(fechas[0].union(*fechas[1:]).order_by("-published_at")[:1]), None)


def participants_prefetch():
    """La precarga de quienes participan en una publicación, una actividad o un registro, cada
    persona con `has_page` (`Contributor.objects.with_page()`): «Participan» y el pie de la
    ficha la enlazan solo si tiene ficha, y lo saben con la misma consulta de la lista."""
    return Prefetch("participants", queryset=Contributor.objects.with_page())


# Las columnas de cada fila de `coincidencias_por_nombre`, en este orden.
COLUMNAS_DE_COINCIDENCIA = (
    "tipo",
    "slug",
    "titulo",
    "dato",
    "lugar",
    "fecha",
    "anio",
    "integrante",
)


def _columnas(filas, tipo, titulo, dato="", lugar="", fecha=None, anio=None, integrante=None):
    """Las columnas de una parte de la UNION. Todas son anotaciones y van en el mismo orden
    en las cuatro partes: la UNION empareja las columnas por su posición, no por su nombre.
    Un hueco es un NULL con su tipo (`Cast`): PostgreSQL resuelve los tipos de la UNION de
    dos en dos, y dos NULL sin tipo quedarían como texto, que luego no casa con una fecha."""
    nombres = [f"r_{c}" for c in COLUMNAS_DE_COINCIDENCIA]
    valores = (
        Value(tipo),
        F("slug"),
        F(titulo),
        F(dato) if dato else Value(""),
        F(lugar) if lugar else Value(""),
        F(fecha) if fecha else Cast(Value(None), DateTimeField()),
        anio if anio is not None else Cast(Value(None), IntegerField()),
        F(integrante) if integrante else Value(False),
    )
    return filas.annotate(**dict(zip(nombres, valores, strict=True))).values_list(*nombres)


# Los tipos de la búsqueda, en el orden en que se enseñan sus grupos: quien busca un nombre lo
# encuentra arriba; después, la obra en el orden de la barra, y las actividades. Los textos y
# los poemas salen de la búsqueda de texto completo; los demás, de coincidencias_por_nombre.
PERSON, POEM, TEXT, RECORDING, PUBLICATION, EVENT = (
    "persona",
    "poema",
    "texto",
    "registro",
    "publicacion",
    "actividad",
)
SEARCH_TYPES = (
    (PERSON, "Personas"),
    (POEM, "Poemas"),
    (TEXT, "Textos"),
    (RECORDING, "Registros"),
    (PUBLICATION, "Publicaciones"),
    (EVENT, "Actividades"),
)


def coincidencias_por_nombre(termino, tope):
    """Personas, registros, publicaciones y actividades cuyo nombre o título contiene el
    término, sin distinguir acentos ni mayúsculas: la base quita los acentos de los dos lados
    (`unaccent`). Es UNA consulta: las cuatro partes van unidas
    (UNION ALL), cada una con su orden y su tope. Con una consulta por tipo, la búsqueda
    pasaría del techo de diez consultas de su prueba de rendimiento.

    Cada fila trae las columnas de COLUMNAS_DE_COINCIDENCIA; `tipo` dice qué es y cómo se
    enlaza. Las personas son las integrantes, también las históricas, y quien firma algo
    publicado: una firma sin nada publicado no tiene qué enseñar en su página."""
    personas = _columnas(
        Contributor.objects.visible().filter(display_name__unaccent__icontains=termino),
        PERSON,
        "display_name",
        dato="role",
        integrante="is_member",
    ).order_by("-is_member", "display_name")[:tope]
    registros = _columnas(
        Recording.objects.published().filter(title__unaccent__icontains=termino),
        RECORDING,
        "title",
        dato="kind",
        anio=ExtractYear("recorded_on"),
    ).order_by("-recorded_on", "-created_at")[:tope]
    publicaciones = _columnas(
        Publication.objects.published().filter(title__unaccent__icontains=termino),
        PUBLICATION,
        "title",
        dato="kind",
        anio=F("year"),
    ).order_by("position", "-year", "title")[:tope]
    actividades = _columnas(
        Event.objects.published().filter(title__unaccent__icontains=termino),
        EVENT,
        "title",
        dato="type",
        lugar="city",
        fecha="starts_at",
    ).order_by("-starts_at")[:tope]
    return [
        dict(zip(COLUMNAS_DE_COINCIDENCIA, fila, strict=True))
        for fila in personas.union(registros, publicaciones, actividades, all=True)
    ]
