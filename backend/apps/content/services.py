"""Consultas de contenido que usan varias apps (la portada, el dossier, la búsqueda)."""

from django.db.models import DateTimeField, F, IntegerField, Value
from django.db.models.functions import Cast, ExtractYear

from apps.media.models import Recording

from .models import Article, Poem


def ultima_publicacion():
    """Cuándo publicó el colectivo por última vez: un poema, un texto o un registro. Es el
    «Actualizado el…» del cierre de la portada y de la ficha del dossier, en una sola consulta.
    Cuenta la fecha de publicación y no la de edición: corregir una errata no hace más reciente
    la portada."""
    fechas = (
        Article.objects.published()
        .filter(published_at__isnull=False)
        .order_by()
        .values_list("published_at", flat=True)
        .union(
            Poem.objects.published()
            .filter(published_at__isnull=False)
            .order_by()
            .values_list("published_at", flat=True),
            Recording.objects.published()
            .filter(published_at__isnull=False)
            .order_by()
            .values_list("published_at", flat=True),
        )
        .order_by("-published_at")
    )
    return next(iter(fechas[:1]), None)


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
    dos en dos, y dos NULL sin tipo quedaban como texto, que luego no casaba con una fecha."""
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


def coincidencias_por_nombre(termino, tope):
    """Personas, registros, publicaciones y actividades cuyo nombre o título contiene el
    término, sin distinguir acentos ni mayúsculas: `termino` llega sin acentos y la base
    quita los de la columna (`unaccent`). Es UNA consulta: las cuatro partes van unidas
    (UNION ALL), cada una con su orden y su tope. Con una consulta por tipo, la búsqueda
    pasaba del techo de diez consultas de su prueba de rendimiento.

    Cada fila trae las columnas de COLUMNAS_DE_COINCIDENCIA; `tipo` dice qué es y cómo se
    enlaza. Las personas son las integrantes, también las históricas, y quien firma algo
    publicado: una firma sin nada publicado no tiene qué enseñar en su página."""
    from apps.agenda.models import Event
    from apps.people.models import Contributor
    from apps.showcase.models import Publication

    personas = _columnas(
        Contributor.objects.visible().filter(display_name__unaccent__icontains=termino),
        "persona",
        "display_name",
        dato="role",
        integrante="is_member",
    ).order_by("-is_member", "display_name")[:tope]
    registros = _columnas(
        Recording.objects.published().filter(title__unaccent__icontains=termino),
        "registro",
        "title",
        dato="kind",
        anio=ExtractYear("recorded_on"),
    ).order_by("-recorded_on", "-created_at")[:tope]
    publicaciones = _columnas(
        Publication.objects.published().filter(title__unaccent__icontains=termino),
        "publicacion",
        "title",
        dato="kind",
        anio=F("year"),
    ).order_by("position", "-year", "title")[:tope]
    actividades = _columnas(
        Event.objects.published().filter(title__unaccent__icontains=termino),
        "actividad",
        "title",
        dato="type",
        lugar="city",
        fecha="starts_at",
    ).order_by("-starts_at")[:tope]
    return [
        dict(zip(COLUMNAS_DE_COINCIDENCIA, fila, strict=True))
        for fila in personas.union(registros, publicaciones, actividades, all=True)
    ]
