"""Etiquetas para renderizar imágenes responsivas (srcset + width/height + lazy)."""

from django import template
from django.templatetags.static import static

register = template.Library()

# La portada pasa al recorte vertical en el mismo ancho en que el logo pasa a dos líneas.
PORTADA_TELEFONO = "(max-width: 719px)"
# La lámina del estreno (D18): la obra de la portada mientras el colectivo no elija la suya.
# Ancho × alto de cada copia en static/img/portada/.
LAMINA = {
    "ancha": ((960, 600), (1440, 900), (1920, 1200), (2400, 1500)),
    "alta": ((640, 1280), (960, 1920), (1080, 2160)),
}


@register.inclusion_tag("media/partials/_responsive_img.html")
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


def _pintada(proporcion, asomo):
    """Lo que mide pintada una obra de esa proporción (ancho / alto). La obra mide el ancho de
    la ventana y de alto max(460px, 100svh - asomo) (ver site.css), y con object-fit: cover la
    imagen crece hasta cubrirla: se pinta al ancho de la ventana o al alto de la obra por su
    proporción, lo que sea mayor. Con «100vw» el navegador elegía una copia más chica que lo
    pintado: a 951 px, la de 960 para una lámina pintada a 1261. vh y no svh: en `sizes` es
    lo que entienden todos los navegadores."""
    return f"max(100vw, {round(460 * proporcion)}px, (100vh - {asomo}px) * {proporcion:.3f})"


def _sizes(ancho, alto, solo_telefono):
    """`sizes` de una fuente de la portada: el asomo mide 96 px en el teléfono y 112 desde
    720 px. La fuente del teléfono solo se usa ahí; las demás, en cualquier ancho."""
    if not ancho or not alto:
        return "100vw"
    proporcion = ancho / alto
    if solo_telefono:
        return _pintada(proporcion, 96)
    return f"{PORTADA_TELEFONO} {_pintada(proporcion, 96)}, {_pintada(proporcion, 112)}"


def _fuente(media, ext, srcset, ancho, alto):
    return {
        "media": media,
        "type": f"image/{ext}",
        "srcset": srcset,
        "sizes": _sizes(ancho, alto, solo_telefono=bool(media)),
        "width": ancho,
        "height": alto,
    }


def _fuentes_del_recurso(recurso, media):
    """Las <source> de un recurso de portada: AVIF y WebP, con las copias que existan."""
    fuentes = []
    for ext, _, _ in recurso.PORTADA_FORMATS:
        srcset = recurso.portada_srcset(ext)
        if srcset:
            fuentes.append(_fuente(media, ext, srcset, recurso.width, recurso.height))
    return fuentes


def _lamina():
    def srcset(forma, ext):
        return ", ".join(
            f"{static(f'img/portada/lamina-{forma}-{w}.{ext}')} {w}w" for w, _ in LAMINA[forma]
        )

    (ancho_alta, alto_alta), (ancho, alto) = LAMINA["alta"][-1], LAMINA["ancha"][-1]
    fuentes = [
        _fuente(PORTADA_TELEFONO, ext, srcset("alta", ext), ancho_alta, alto_alta)
        for ext in ("avif", "webp")
    ] + [_fuente("", ext, srcset("ancha", ext), ancho, alto) for ext in ("avif", "webp")]
    return {
        "fuentes": fuentes,
        "src": static("img/portada/lamina-ancha-1440.jpg"),
        "srcset": "",
        "sizes": "",
        "width": ancho,
        "height": alto,
        "alt": "",
    }


@register.inclusion_tag("media/partials/_portada_img.html")
def portada_img(imagen=None, telefono=None):
    """La obra de la portada (D18): un <picture> con AVIF y WebP, el recorte vertical para el
    teléfono si lo hay, y prioridad alta, porque es lo primero que se pinta. Nunca sirve el
    archivo subido: las copias de portada llegan a su ancho, y el <img> de reserva usa las
    copias de siempre sin el original. Sin imagen elegida, la lámina del colectivo.

    El texto alternativo es el del recurso: la imagen que elige el colectivo es suya y dice
    algo. La lámina es ambiente y va con `alt=""`."""
    if imagen is None:
        return _lamina()
    fuentes = []
    if telefono is not None:
        fuentes += _fuentes_del_recurso(telefono, PORTADA_TELEFONO)
    fuentes += _fuentes_del_recurso(imagen, "")
    # La reserva, para el navegador que no conoce AVIF ni WebP: las copias de `srcset` de
    # siempre, sin el original. Una imagen más chica que todas ellas no tiene copias, y
    # entonces el original es chico.
    copias = [
        parte
        for parte in imagen.srcset().split(", ")
        if parte and not parte.startswith(f"{imagen.file.url} ")
    ]
    src = copias[-1].rsplit(" ", 1)[0] if copias else imagen.file.url
    return {
        "fuentes": fuentes,
        "src": src,
        "srcset": ", ".join(copias),
        "sizes": _sizes(imagen.width, imagen.height, solo_telefono=False),
        "width": imagen.width,
        "height": imagen.height,
        "alt": imagen.alt_text,
    }
