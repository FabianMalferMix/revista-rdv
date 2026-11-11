"""La navegación del sitio, en una sola estructura: los grupos del mapa con sus enlaces, y la barra
de la cabecera. De ella salen la barra, la sub-fila de los índices y el mapa del sitio (el del pie y
el del menú del teléfono), que el procesador de contexto `nav` entrega a las plantillas.

Cada enlace se escribe una vez, en su grupo; la barra nombra enlaces y grupos del mapa y no tiene
enlaces propios. Lo que no es una página del sitio no va aquí: el correo, las redes, RSS y Podcast
los escribe la plantilla del mapa (partials/_mapa.html).
"""

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class Link:
    """Una página del sitio: su rótulo y su vista. `pages` son las vistas que están en su lugar
    sin ser ella: la ficha de un poema está en «Poemas», y la barra lo marca ahí."""

    label: str
    view: str
    pages: tuple[str, ...] = ()

    @property
    def views(self):
        return (self.view, *self.pages)


@dataclass(frozen=True)
class Group:
    """Un grupo del mapa: su encabezado y sus enlaces, en el orden en que se leen en el mapa y en
    la sub-fila.

    - `label`: el grupo entra entero en la barra con este rótulo; lleva a su primer enlace y marca
      todas sus vistas.
    - `subnav`: cada índice del grupo lleva en su cabecera la sub-fila con el grupo entero.
    - `contact`: el mapa cierra el grupo con el correo del colectivo.
    """

    title: str
    links: tuple[Link, ...]
    label: str = ""
    subnav: bool = False
    contact: bool = False

    @property
    def view(self):
        return self.links[0].view

    @property
    def views(self):
        return tuple(view for link in self.links for view in link.views)


MEMBERS = Link("Integrantes", "people:member_index", pages=("people:member_detail",))
AGENDA = Link("Agenda", "agenda:agenda", pages=("agenda:event_detail",))
TRACK_RECORD = Link("Trayectoria", "agenda:trayectoria")
GALLERY = Link("Galería", "agenda:gallery")

POEMS = Link("Poemas", "content:poem_index", pages=("content:poem_detail",))
# Las fichas de una obra reseñada, su editorial y su autor están en «Textos»: se llega a ellas
# desde una reseña.
TEXTS = Link(
    "Textos",
    "content:text_archive",
    pages=(
        "content:article_detail",
        "content:section_detail",
        "content:tag_detail",
        "reviews:work_detail",
        "reviews:publisher_detail",
        "reviews:bookauthor_detail",
    ),
)
COLLECTIONS = Link("Colecciones", "content:collection_index")
RECORDINGS = Link("Registros", "media:recording_index", pages=("media:recording_detail",))
PUBLICATIONS = Link(
    "Publicaciones", "showcase:publication_index", pages=("showcase:publication_detail",)
)

DOSSIER = Link("Dossier", "showcase:dossier")
PRESS = Link("Prensa", "showcase:press_index")
PARTNERS = Link("Aliados", "showcase:partner_index")
SUBMIT = Link("Enviar una propuesta", "submissions:submit")

COLLECTIVE = Group(
    "El colectivo", (MEMBERS, AGENDA, TRACK_RECORD, GALLERY), label="Colectivo", subnav=True
)
WORK = Group("La obra", (POEMS, TEXTS, COLLECTIONS, RECORDINGS, PUBLICATIONS))
PRESS_AND_MANAGEMENT = Group(
    "Prensa y gestión", (DOSSIER, PRESS, PARTNERS, SUBMIT), subnav=True, contact=True
)

# El mapa del sitio: sus grupos, en orden.
MAP = (COLLECTIVE, WORK, PRESS_AND_MANAGEMENT)

# La barra: cuatro páginas de la obra y el colectivo entero, que lleva a Integrantes. Las
# colecciones y las fichas de colaborador no marcan ninguna entrada: reúnen poemas y textos.
# Prensa y gestión no está en la barra: se llega desde el mapa, y al dossier también desde su
# botón de la cabecera.
BAR = (POEMS, TEXTS, RECORDINGS, PUBLICATIONS, COLLECTIVE)


def bar(view):
    """La barra, con lo actual marcado. `actual` es el valor de `aria-current`: «page» en la
    página de la entrada y «true» en otra de su lugar (la ficha de un poema no es la página
    «Poemas», pero está en ella)."""
    return [
        {
            "rotulo": entry.label,
            "url": reverse(entry.view),
            "actual": "page" if view == entry.view else ("true" if view in entry.views else ""),
        }
        for entry in BAR
    ]


def subnav(view):
    """La sub-fila de la página: en una página de un grupo que la lleva, el grupo entero con la
    página marcada; en cualquier otra, nada. La pintan los índices, en su cabecera
    (partials/_index_head.html); el dossier y el formulario de envío no la llevan."""
    for group in MAP:
        if group.subnav and view in {link.view for link in group.links}:
            return {
                "titulo": group.title,
                "enlaces": [
                    {
                        "rotulo": link.label,
                        "url": reverse(link.view),
                        "actual": "page" if view == link.view else "",
                    }
                    for link in group.links
                ],
            }
    return None


def site_map():
    """Los grupos del mapa con sus enlaces, para el pie y el menú del teléfono."""
    return [
        {
            "titulo": group.title,
            "enlaces": [{"rotulo": link.label, "url": reverse(link.view)} for link in group.links],
            "contacto": group.contact,
        }
        for group in MAP
    ]
