"""Etiquetas para renderizar imágenes responsivas (srcset + width/height + lazy)."""

from django import template

from config.breakpoints import ESTANTE_WIDE, LECTURA_SALA, PHONE, below, from_cut

register = template.Library()

# Lo que mide pintada cada imagen cuyo ancho cambia con la ventana, por su nombre: los tramos
# que empiezan o terminan en un corte de la hoja (`config/breakpoints.py`), en orden, y lo que
# mide en los demás anchos. Donde crece con la ventana hasta un tope, `min()` lo dice sin
# un corte. Un ancho fijo (`96px`) se escribe en la plantilla: no depende de ningún corte.
SIZES = {
    "afiche-ficha": ([(below(PHONE), "60vw")], "420px"),
    "cubierta-texto": ([(below(LECTURA_SALA), "92vw")], "760px"),
    "ficha-medio": ([(below(PHONE), "60vw")], "320px"),
    "galeria-primera": ([(below(PHONE), "62vw")], "min(31vw, 440px)"),
    "galeria-resto": ([(below(PHONE), "31vw")], "min(16vw, 220px)"),
    "miniatura-fila": ([(below(PHONE), "64px")], "96px"),
    "placa-pliego": ([(below(PHONE), "92vw")], "440px"),
    "poster-indice": ([(below(PHONE), "92vw")], "min(46vw, 660px)"),
    "poster-reproductor": ([], "min(92vw, 780px)"),
    "retrato-colectivo": ([(below(PHONE), "45vw")], "290px"),
    "retrato-portada": ([(below(PHONE), "31vw")], "210px"),
    "tapa-catalogo": ([], "min(45vw, 240px)"),
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
