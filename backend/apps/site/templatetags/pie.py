"""Las salidas al pie de cada ficha y del cierre de la portada, con sus rótulos.

Cada ficha tiene su etiqueta, que arma la lista de puertas (un rótulo que dice qué es, «Más
de» o «Índice», y el destino) y la dibuja con `partials/_pie_de_entidad.html`. Las vecinas, que
son consultas, las busca la vista con `apps/site/pie.py` y llegan como `neighbors`, el par
(anterior, siguiente).
"""

from django import template
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import url_for_year

register = template.Library()

PIE = "partials/_pie_de_entidad.html"


def puerta(rotulo, texto, url):
    """Una salida: un rótulo que dice qué es («Más de», «Índice») y el destino."""
    return {"rotulo": rotulo, "texto": texto, "url": url}


def firmas(personas):
    """Una puerta por cada persona que firma, hacia su página."""
    return [puerta("Más de", p.display_name, p.get_absolute_url()) for p in personas]


def puertas_vecinas(neighbors, nombre, titulo):
    """Las puertas «{nombre} anterior» y «{nombre} siguiente», las que haya."""
    anterior, siguiente = neighbors
    puertas = []
    if anterior:
        puertas.append(puerta(f"{nombre} anterior", titulo(anterior), anterior.get_absolute_url()))
    if siguiente:
        puertas.append(
            puerta(f"{nombre} siguiente", titulo(siguiente), siguiente.get_absolute_url())
        )
    return puertas


@register.inclusion_tag(PIE)
def article_pie(article, neighbors):
    pie = [puerta("Índice", "Todos los textos", reverse("content:text_archive"))]
    if article.section:
        pie.append(puerta("Sección", article.section.name, article.section.get_absolute_url()))
    pie += firmas(article.bylines)
    pie += puertas_vecinas(neighbors, "Texto", lambda a: a.title)
    return {"pie": pie}


@register.inclusion_tag(PIE)
def poem_pie(poem, colecciones, neighbors):
    pie = [puerta("Índice", "Todos los poemas", reverse("content:poem_index"))]
    pie += firmas(poem.bylines)
    pie += [puerta("En la colección", c.title, c.get_absolute_url()) for c in colecciones]
    pie += puertas_vecinas(neighbors, "Poema", lambda p: p.title)
    return {"pie": pie}


@register.inclusion_tag(PIE)
def recording_pie(recording, poems, neighbors):
    pie = [puerta("Índice", "Todos los registros", reverse("media:recording_index"))]
    pie += [puerta("Poema registrado", p.title, p.get_absolute_url()) for p in poems]
    if evento := recording.public_event:
        pie.append(puerta("Evento", evento.title, evento.get_absolute_url()))
    pie += puertas_vecinas(neighbors, "Registro", lambda r: r.title)
    return {"pie": pie}


@register.inclusion_tag(PIE)
def event_pie(event, neighbors):
    """Una actividad pasada lleva a su año en la trayectoria; una por venir, a la agenda. Las
    vecinas van por fecha: «anterior» es la de antes en el tiempo."""
    if event.is_past:
        anio = timezone.localtime(event.starts_at).year
        pie = [puerta("Trayectoria", str(anio), url_for_year(anio))]
    else:
        pie = [puerta("Índice", "Agenda", reverse("agenda:agenda"))]
    if event.photos.all():
        pie.append(puerta("Fotos", "Galería", reverse("agenda:gallery")))
    pie.append(puerta("Para programar", "Dossier", reverse("showcase:dossier")))
    pie += puertas_vecinas(neighbors, "Actividad", lambda e: e.title)
    return {"pie": pie}


@register.inclusion_tag(PIE)
def publication_pie(publication, neighbors):
    pie = [puerta("Índice", "Todas las publicaciones", reverse("showcase:publication_index"))]
    if publication.publisher:
        pie.append(
            puerta(
                "Editorial", publication.publisher.name, publication.publisher.get_absolute_url()
            )
        )
    if publication.year:
        pie.append(puerta("Trayectoria", str(publication.year), url_for_year(publication.year)))
    # Quien participa sin ficha (`has_page`, de la precarga de la vista) no tiene puerta: no
    # hay adónde ir.
    pie += firmas(p for p in publication.participants.all() if p.has_page)
    pie += puertas_vecinas(neighbors, "Publicación", lambda p: p.title)
    return {"pie": pie}


@register.inclusion_tag(PIE)
def member_pie(neighbors):
    return {
        "pie": [
            puerta("Índice", "Todo el colectivo", reverse("people:member_index")),
            *puertas_vecinas(neighbors, "Integrante", lambda c: c.display_name),
            puerta("El colectivo", "Trayectoria", reverse("agenda:trayectoria")),
            puerta("Para programar", "Dossier", reverse("showcase:dossier")),
        ]
    }


@register.inclusion_tag(PIE)
def cierre_pie(correo, etiqueta):
    """Las puertas del cierre de la portada, para programadores y jurados: lo que piden, y el
    correo de contacto si el colectivo tiene uno."""
    pie = [
        puerta("Kit de prensa", "Dossier", reverse("showcase:dossier")),
        puerta("Notas y entrevistas", "Prensa", reverse("showcase:press_index")),
        puerta("Quiénes nos apoyan", "Aliados", reverse("showcase:partner_index")),
    ]
    if correo:
        pie.append(puerta("Contacto", "Escríbenos", f"mailto:{correo}"))
    return {"pie": pie, "etiqueta": etiqueta}
