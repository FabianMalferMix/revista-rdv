"""Etiquetas para renderizar imágenes responsivas (srcset + width/height + lazy)."""

from django import template

from apps.site.portada import A_LA_VISTA, A_LA_VISTA_TELEFONO
from config.breakpoints import (
    CARRIL_WIDE,
    ESTANTE_WIDE,
    LECTURA_SALA,
    MEASURE,
    PHONE,
    TIRADA_WIDE,
    WIDE_FROM_CARRIL,
    below,
    from_cut,
    lane,
)

register = template.Library()

LANE = lane()
LANE_FROM_CARRIL = lane(WIDE_FROM_CARRIL)
# El carril de lectura, donde van la ficha de un registro y la de una editorial.
CONTENT_LANE = lane(MEASURE)


def _column(count, gap, width=LANE):
    """Una de `count` columnas iguales de `width`, con `gap` px entre cada dos."""
    return f"calc(({width} - {(count - 1) * gap}px) / {count})"


def _reading(width):
    """El texto de la sala de lectura (`.lectura-sala`): siete onceavos de `width`, tras el
    hueco entre el ancla y el texto."""
    return f"calc(({width} - clamp(32px, 5vw, 96px)) * 7 / 11)"


# Un álbum de la galería (`.album-grid`, columnas de 440 px o más y 28 px entre ellas): uno por
# fila, de 880 px como mucho; dos cuando caben, que con el carril de TIRADA_WIDE ya caben, y tres
# con el de CARRIL_WIDE.
ALBUM = (
    [
        (below(TIRADA_WIDE), f"min(880px, {LANE})"),
        (from_cut(CARRIL_WIDE), _column(3, 28, LANE_FROM_CARRIL)),
    ],
    _column(2, 28),
)


def _sheet(share):
    """Una foto de la hoja de contactos de un álbum (`.hoja`: 2fr 1fr, con 6 px entre las dos
    columnas). Sola, ocupa la hoja entera."""

    def part(album):
        return {
            "sola": album,
            "primera": f"calc(({album} - 6px) * 2 / 3)",
            "resto": f"calc(({album} - 6px) / 3)",
        }[share]

    tramos, resto = ALBUM
    return [(media, part(width)) for media, width in tramos], part(resto)


# Lo que mide pintada cada imagen cuyo ancho cambia con la ventana, por su nombre: los tramos
# que empiezan o terminan en un corte de la hoja (`config/breakpoints.py`), en orden, y lo que
# mide en los demás anchos. Casi todas miden una parte del carril ancho (`lane()`), que crece
# con la ventana hasta su tope y desde CARRIL_WIDE tiene otro. Un ancho fijo (`96px`) se
# escribe en la plantilla: no depende de ningún corte.
#
# Una rejilla que pone tantas columnas como caben (`auto-fill`, `auto-fit`) no cambia en un
# corte de la hoja: cada tramo pide las columnas que tiene la rejilla en la mayor parte de él.
# `tools/ux/browser-smoke.js` compara, a 951 y a 390 px, lo que pide cada imagen con lo que
# pinta.
SIZES = {
    # La ficha de un evento (`.ficha-cabecera--afiche`): hasta 420 px, al lado de una columna de
    # 360 px como poco; en el teléfono, la de `.ficha-medio`, de 260 px.
    "afiche-ficha": (
        [(below(PHONE), f"min(260px, {LANE})")],
        f"min(420px, {LANE} - clamp(24px, 5vw, 80px) - 360px)",
    ),
    # Una fecha de la agenda (`.event-afiche`): un cuarto de su tarjeta y 128 px como mucho. Las
    # tarjetas son las columnas de `.event-list`, de 440 px o más: una, dos desde TIRADA_WIDE y
    # tres con el carril de CARRIL_WIDE.
    "afiche-agenda": (
        [
            (below(TIRADA_WIDE), f"min(128px, {LANE} / 4)"),
            (from_cut(CARRIL_WIDE), f"min(128px, {_column(3, 28, LANE_FROM_CARRIL)} / 4)"),
        ],
        f"min(128px, {_column(2, 28)} / 4)",
    ),
    # La hoja de contactos de la tirada (`.tirada-contacto`).
    "contacto-tirada": ([(below(PHONE), "64px")], "96px"),
    # La imagen de un texto: a todo el carril, y al lado del ancla desde LECTURA_SALA.
    "cubierta-texto": (
        [(below(LECTURA_SALA), LANE), (from_cut(CARRIL_WIDE), _reading(LANE_FROM_CARRIL))],
        _reading(LANE),
    ),
    # La ficha de una persona o de una publicación (`.ficha-cabecera`): su columna de 320 px; en
    # el teléfono, `.ficha-medio`, de 260 px.
    "ficha-medio": ([(below(PHONE), f"min(260px, {LANE})")], "320px"),
    "galeria-primera": _sheet("primera"),
    "galeria-resto": _sheet("resto"),
    "galeria-sola": _sheet("sola"),
    # La miniatura de una fila (`.fila-miniatura`): 72 px donde la lista mide 700 px o más
    # (`@container filas`). `sizes` no ve el contenedor: en la portada, donde la lista es más
    # estrecha, la caja mide 56, y la foto, recortada a 3:4, la cubre con más ancho si es apaisada.
    "miniatura-fila": ([(below(PHONE), "56px")], "72px"),
    # La placa de un pliego de la tirada (`--pliego` en componentes.css): el pliego menos su
    # margen de 176 px, sus 24 px de borde a cada lado y los 24 entre la placa y el margen. En el
    # teléfono va a sangre del pliego.
    "placa-pliego": (
        [
            (below(PHONE), f"calc({LANE} - 70px)"),
            (below(TIRADA_WIDE), "min(312px, 62vw - 248px)"),
        ],
        f"min(312px, ({LANE} - 320px) * 0.64 - 248px)",
    ),
    # Un registro en el índice (`.recording-list`, columnas de 380 px o más): uno por fila, de
    # 720 px como mucho; dos desde LECTURA_SALA y tres desde ESTANTE_WIDE.
    "poster-indice": (
        [
            (below(LECTURA_SALA), f"min(720px, {LANE})"),
            (below(ESTANTE_WIDE), _column(2, 28)),
            (from_cut(CARRIL_WIDE), _column(3, 28, LANE_FROM_CARRIL)),
        ],
        _column(3, 28),
    ),
    # El afiche de un registro de audio (`.player-audio > .riso-duo`): el 30 % del carril de
    # lectura, entre 120 y 240 px.
    "poster-audio": ([], f"clamp(120px, {CONTENT_LANE} * 0.3, 240px)"),
    "poster-reproductor": ([], "min(92vw, 780px)"),
    # Una integrante en el índice (`.member-grid`): columnas de 150 px o más en el teléfono (dos)
    # y de 220 px o más desde PHONE: tres, cuatro desde TIRADA_WIDE, cinco desde ESTANTE_WIDE y
    # seis con el carril de CARRIL_WIDE.
    "retrato-colectivo": (
        [
            (below(PHONE), _column(2, 24)),
            (below(TIRADA_WIDE), _column(3, 24)),
            (below(ESTANTE_WIDE), _column(4, 24)),
            (from_cut(CARRIL_WIDE), _column(6, 24, LANE_FROM_CARRIL)),
        ],
        _column(5, 24),
    ),
    # «Las voces» de la portada (`.integrantes-fila`): A_LA_VISTA retratos con 12 px entre ellos,
    # al lado de los 216 px del texto y 40 px de hueco; en el teléfono, A_LA_VISTA_TELEFONO a
    # todo el carril, con 10.
    "retrato-portada": (
        [
            (below(PHONE), _column(A_LA_VISTA_TELEFONO, 10)),
            (from_cut(CARRIL_WIDE), _column(A_LA_VISTA, 12, f"({LANE_FROM_CARRIL} - 256px)")),
        ],
        _column(A_LA_VISTA, 12, f"({LANE} - 256px)"),
    ),
    # Una publicación del catálogo (`.pub-grid`): columnas de 150 px o más en el teléfono (dos) y
    # de 240 px o más desde PHONE: dos, tres desde LECTURA_SALA, cuatro desde TIRADA_WIDE y cinco
    # desde ESTANTE_WIDE.
    "tapa-catalogo": (
        [
            (below(PHONE), _column(2, 20)),
            (below(LECTURA_SALA), _column(2, 28)),
            (below(TIRADA_WIDE), _column(3, 28)),
            (below(ESTANTE_WIDE), _column(4, 28)),
            (from_cut(CARRIL_WIDE), _column(5, 28, LANE_FROM_CARRIL)),
        ],
        _column(5, 28),
    ),
    # Una publicación en la ficha de una editorial (`.pub-grid` en el carril de lectura): dos por
    # fila hasta LECTURA_SALA, y desde ahí tres, las que caben de 240 px.
    "tapa-editorial": (
        [
            (below(PHONE), _column(2, 20, CONTENT_LANE)),
            (below(LECTURA_SALA), _column(2, 28, CONTENT_LANE)),
        ],
        _column(3, 28, CONTENT_LANE),
    ),
    "tapa-estante": ([(below(PHONE), "160px"), (from_cut(ESTANTE_WIDE), "270px")], "200px"),
}


@register.simple_tag
def sizes(slot):
    """El `sizes` de una imagen cuyo ancho cambia con la ventana, por su nombre en `SIZES`:
    `{% sizes "tapa-estante" as sizes %}` y después `{% responsive_img … sizes=sizes %}`. Un
    nombre que no está es un error de la plantilla, no una imagen sin `sizes`."""
    if slot not in SIZES:
        raise ValueError(f"No hay sizes para «{slot}»: los nombres están en SIZES")
    tramos, resto = SIZES[slot]
    return ", ".join([*(f"{media} {ancho}" for media, ancho in tramos), resto])


@register.inclusion_tag("partials/_responsive_img.html")
def responsive_img(asset, sizes="100vw", css_class="", lazy=True, alt=None, decorativa=False):
    """Renderiza un <img> con srcset (si hay derivados), width/height (anti-CLS) y
    decoding async. `lazy=False` para imágenes destacadas sobre el pliegue (LCP).

    `decorativa=True` emite `alt=""`: la imagen acompaña a un texto que ya la nombra y
    un lector de pantalla no debe leerla. No se consigue pasando `alt=""`: un `alt`
    vacío cae al texto alternativo del recurso, y de eso dependen las fotos cuyo pie
    está en blanco."""
    return {
        "url": asset.file.url,
        "srcset": asset.srcset(),
        "sizes": sizes,
        "width": asset.width,
        "height": asset.height,
        "alt": "" if decorativa else (alt or asset.alt_text),
        "css_class": css_class,
        "lazy": lazy,
    }
