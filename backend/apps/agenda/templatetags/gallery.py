"""El atributo `sizes` de cada foto del mosaico de un evento: pide lo que ocupa."""

from django import template

from config.breakpoints import CARRIL_WIDE, WIDE_FROM_CARRIL, from_cut, lane

register = template.Library()

# El mosaico (`.photo-grid` en componentes.css): seis columnas a todo el carril ancho, con 6 px
# entre cada dos, y hasta seis fotos; las demás van a tercios en «Ver las N fotos».
MOSAIC_COLUMNS = 6
MOSAIC_GAP = 6
MOSAIC_TILES = 6


def _columns(numero, total):
    """Las columnas que ocupa la foto `numero` de `total`, con las reglas de componentes.css:
    con una, todo el ancho; con dos o cuatro, a medias; con cinco, dos a medias y tres a
    tercios; con tres, o con seis o más, la primera a doble tamaño y las demás a tercios."""
    if numero > MOSAIC_TILES:
        return 2
    if total == 1:
        return MOSAIC_COLUMNS
    if total in (2, 4) or (total == 5 and numero <= 2):
        return 3
    if numero == 1 and (total == 3 or total >= MOSAIC_TILES):
        return 4
    return 2


def _tile(columnas, carril):
    """Lo que mide una foto de `columnas` columnas del mosaico en un carril de `carril`: su
    parte del carril y de los huecos, menos el que la separa de la siguiente."""
    return f"calc(({carril} + {MOSAIC_GAP}px) * {columnas} / {MOSAIC_COLUMNS} - {MOSAIC_GAP}px)"


@register.simple_tag
def photo_sizes(numero, total):
    """El `sizes` de la foto `numero` de `total`: su parte del carril ancho, que desde
    CARRIL_WIDE tiene otro tope."""
    columnas = _columns(numero, total)
    return (
        f"{from_cut(CARRIL_WIDE)} {_tile(columnas, lane(WIDE_FROM_CARRIL))}, "
        f"{_tile(columnas, lane())}"
    )
