"""El atributo `sizes` de cada foto del mosaico de un evento: pide lo que ocupa."""

from django import template

register = template.Library()

# El mosaico (`.photo-grid` en site.css): seis columnas, como mucho el ancho del carril, y
# hasta seis fotos; las demás van a tercios en «Ver las N fotos».
MOSAIC_WIDTH = 1320
MOSAIC_COLUMNS = 6
MOSAIC_TILES = 6


def _columns(numero, total):
    """Las columnas que ocupa la foto `numero` de `total`, con las reglas de site.css: con una,
    todo el ancho; con dos o cuatro, a medias; con cinco, dos a medias y tres a tercios; con
    tres, o con seis o más, la primera a doble tamaño y las demás a tercios."""
    if numero > MOSAIC_TILES:
        return 2
    if total == 1:
        return 6
    if total in (2, 4) or (total == 5 and numero <= 2):
        return 3
    if numero == 1 and (total == 3 or total >= MOSAIC_TILES):
        return 4
    return 2


@register.simple_tag
def photo_sizes(numero, total):
    columnas = _columns(numero, total)
    vw = 100 * columnas // MOSAIC_COLUMNS
    return f"(max-width: 720px) {vw}vw, {MOSAIC_WIDTH * columnas // MOSAIC_COLUMNS}px"
