"""La portada, bloque a bloque: cada constructor reúne lo que enseña su bloque, y la vista de la
portada (`views.home`) solo los junta. `site/home.html` pinta cada bloque desde el suyo: los
constructores traen los datos y los indicadores, y los textos los escribe la plantilla."""

from dataclasses import dataclass
from datetime import date, datetime

from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from apps.agenda.models import Event, EventPhoto
from apps.content.models import Article, Poem
from apps.media.models import TIRADA_SIZE, MediaAsset, Recording
from apps.people.models import Contributor
from apps.showcase.models import Publication
from apps.submissions.models import Call
from config.breakpoints import PHONE, below

from .services import ultima_publicacion

# «Las voces»: cinco retratos a la vez, en una fila; en el teléfono, tres. Las demás vienen en la
# página, escondidas, y el relevo las trae de a una. Es la única fuente: la plantilla los pasa a
# integrantes.js por atributos data-, con el corte del teléfono, y la hoja no repite el número.
A_LA_VISTA = 5
A_LA_VISTA_TELEFONO = 3

# El estante: una publicación de frente y hasta siete de lomo, lo que cabe a 951 px junto a la
# ficha. Al frente va la marcada «Destacada» en el panel y, si no hay, la primera según su orden
# («Position»).
ESTANTE = 8

# La tirada: como mucho TIRADA_SIZE registros, el tope que valida el panel.
TOPE_TIRADA = TIRADA_SIZE


@dataclass(frozen=True)
class Arte:
    """La obra de la primera vista: la imagen que el colectivo elige en el perfil del sitio y su
    recorte para el teléfono. Sin imagen, la plantilla pone la lámina."""

    portada_imagen: MediaAsset | None
    portada_telefono: MediaAsset | None


def build_arte(profile):
    return Arte(portada_imagen=profile.hero_image, portada_telefono=profile.hero_image_phone)


@dataclass(frozen=True)
class Hoja:
    """La hoja que sube sobre la obra: lo que dice la cejilla (de dónde es el colectivo y desde
    cuándo, y cuántas son) y, mientras haya una convocatoria abierta, su sello. El Instagram de la
    cejilla lo pone la plantilla, con las redes que ya trae el procesador del perfil."""

    presentacion: list[str]
    member_count: int
    convocatoria: Call | None


def build_hoja(profile, integrantes):
    return Hoja(
        presentacion=profile.presentacion,
        member_count=integrantes,
        convocatoria=Call.objects.open_now().first(),
    )


@dataclass(frozen=True)
class Pliego:
    """Un registro de la tirada: su imagen (el póster o, si no tiene, la primera foto del evento:
    nunca nada con el título impreso, que ya va en grande), el poema que se lee (la plantilla
    cita su primer verso y lo firma), quién lee, el evento publicado (dónde) y cuándo."""

    titulo: str
    url: str
    tipo: str
    duracion: str
    audio: bool
    imagen: MediaAsset | None
    poem: Poem | None
    voces: list[str]
    event: Event | None
    fecha: date | None


@dataclass(frozen=True)
class Tirada:
    """Los registros publicados que el colectivo marcó como destacados, en su orden, cada uno en
    su pliego. Sin ninguno marcado, el registro destacado del perfil del sitio."""

    registros: list[Pliego]


def build_tirada(profile):
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
        return Tirada(registros=[])
    # El poema que se lee en cada registro: el último publicado que lo enlaza.
    poemas = {}
    for poema in (
        Poem.objects.published()
        .filter(recording__in=registros)
        .prefetch_related(Poem.bylines_prefetch())
        .order_by("-published_at")
    ):
        poemas.setdefault(poema.recording_id, poema)
    return Tirada(registros=[_pliego(registro, poemas.get(registro.pk)) for registro in registros])


def _pliego(registro, poema):
    evento = registro.public_event
    fotos = list(evento.photos.all()) if evento else []
    if evento and evento.starts_at:
        cuando = registro.recorded_on or timezone.localtime(evento.starts_at).date()
    else:
        cuando = registro.recorded_on
    return Pliego(
        titulo=registro.title,
        url=registro.get_absolute_url(),
        tipo=registro.get_kind_display(),
        duracion=registro.duracion,
        audio=registro.kind == Recording.Kind.AUDIO,
        imagen=registro.poster or (fotos[0].asset if fotos else None),
        poem=poema,
        voces=[c.display_name for c in registro.participants.all()],
        event=evento,
        fecha=cuando,
    )


def featured_poem(profile, tirada):
    """El poema destacado del perfil, solo si está publicado y en lugar de la tirada: sin ningún
    registro destacado, nunca los dos a la vez."""
    poema = profile.featured_poem
    if tirada.registros or poema is None or not poema.is_published:
        return None
    return poema


def next_event():
    return Event.objects.upcoming().first()


@dataclass(frozen=True)
class Obra:
    """La obra: los últimos poemas, con sus primeros versos, y los últimos textos. El archivo de
    cada uno vive en su índice."""

    poemas: list[Poem]
    articles: QuerySet


def build_obra():
    return Obra(
        # select_related("recording"): la tarjeta de cada poema pregunta por su registro
        # publicado (`published_recording`); sin esto sería una consulta por poema.
        poemas=list(
            Poem.objects.published()
            .select_related("recording")
            .prefetch_related(Poem.bylines_prefetch())[:3]
        ),
        # cover_image: la fila de cada texto enseña su imagen en miniatura.
        articles=Article.objects.published()
        .select_related("section", "cover_image")
        .prefetch_related(Article.bylines_prefetch())[:3],
    )


@dataclass(frozen=True)
class Voces:
    """«Las voces»: todas las integrantes, sin tope, porque a cada una le llega su turno en el
    relevo. Las escondidas solo cuestan su marcado; sus retratos se piden cuando les toca."""

    members: list[Contributor]
    a_la_vista: int = A_LA_VISTA
    a_la_vista_telefono: int = A_LA_VISTA_TELEFONO
    phone_media: str = below(PHONE)

    @property
    def integrantes_vista(self):
        return self.members[: self.a_la_vista]

    @property
    def integrantes_resto(self):
        return self.members[self.a_la_vista :]

    @property
    def relevo_integrantes(self):
        """En el teléfono se ven tres: con cuatro o más ya hay a quién traer deslizando."""
        return len(self.members) > self.a_la_vista_telefono


def build_voces():
    # Se materializa: la hoja dice cuántas son.
    return Voces(members=list(Contributor.objects.members()))


def build_estante():
    """Las publicaciones del estante, las destacadas primero: la primera es la que va de frente.
    Con su editorial, que la ficha nombra: sin ella sería una consulta por publicación."""
    return list(
        Publication.objects.published()
        .select_related("cover", "publisher")
        .order_by("-featured", "position", "-year", "title")[:ESTANTE]
    )


@dataclass(frozen=True)
class Cierre:
    """El cierre, para programadores y jurados: lo último que hizo el colectivo y cuándo publicó
    por última vez. Sus puertas, como las salidas al pie de una ficha, las pone la plantilla
    (`{% cierre_pie %}`)."""

    ultima_actividad: Event | None
    ultima_publicacion: datetime | None


def build_cierre():
    return Cierre(
        ultima_actividad=Event.objects.past().first(),
        ultima_publicacion=ultima_publicacion(),
    )
