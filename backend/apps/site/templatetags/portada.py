"""La obra de la primera vista de la portada (la imagen que elige el colectivo o, sin ella, la
lámina del estreno) y la cuenta del colofón de la tirada, en letras."""

from django import template
from django.templatetags.static import static

from apps.media.models import MediaAsset
from config.breakpoints import PHONE, below

register = template.Library()

# La portada pasa al recorte vertical en el mismo ancho en que el logo pasa a dos líneas.
PORTADA_TELEFONO = below(PHONE)
# Lo que mide la obra en site.css, que `sizes` repite porque no puede leer la hoja: de alto,
# max(MIN_HEIGHT, 100svh - --asomo), donde el asomo es lo que la obra le deja a la hoja en la
# primera vista. `tests/test_portada_obra.py` compara cada número con la hoja.
MIN_HEIGHT = 460
ASOMO = 112
ASOMO_PHONE = 96
# La lámina del estreno: la obra de la portada mientras el colectivo no elija la suya.
# Ancho × alto de cada copia en static/img/portada/, en los formatos de las copias de portada
# (`MediaAsset.PORTADA_FORMATS`). Las rehace desde sus maestras el comando de desarrollo
# `generate_lamina_variants`.
LAMINA = {
    "ancha": ((960, 600), (1440, 900), (1920, 1200), (2400, 1500)),
    "alta": ((640, 1280), (960, 1920), (1080, 2160)),
}
# La reserva del <img>, para el navegador que no conoce AVIF ni WebP: la ancha de 1440 en JPEG.
LAMINA_FALLBACK = ("ancha", 1440, "jpg")


# Cuántos registros tiene la tirada, en letras, para el colofón («cinco registros elegidos por el
# colectivo»): cada cuenta posible hasta el tope de la tirada (`TOPE_TIRADA`, en
# `apps/site/portada.py`), que `tests/test_tirada.py` compara con esta tabla.
NUMERALES = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco"}


@register.filter
def in_words(numero):
    """El número en letras si está en NUMERALES; si no, en cifras."""
    return NUMERALES.get(numero, str(numero))


def lamina_path(forma, width, ext):
    """La ruta de una copia de la lámina, relativa a los estáticos."""
    return f"img/portada/lamina-{forma}-{width}.{ext}"


def _pintada(proporcion, asomo):
    """Lo que mide pintada una obra de esa proporción (ancho / alto). La obra mide el ancho de
    la ventana y de alto max(MIN_HEIGHT, 100svh - asomo), y con object-fit: cover la imagen
    crece hasta cubrirla: se pinta al ancho de la ventana o al alto de la obra por su
    proporción, lo que sea mayor. Con «100vw» el navegador elegía una copia más chica que lo
    pintado: a 951 px, la de 960 para una lámina pintada a 1261. vh y no svh: en `sizes` es
    lo que entienden todos los navegadores."""
    minimo = round(MIN_HEIGHT * proporcion)
    return f"max(100vw, {minimo}px, (100vh - {asomo}px) * {proporcion:.3f})"


def _sizes(ancho, alto, solo_telefono):
    """`sizes` de una fuente de la portada, con el asomo del teléfono o el de la pantalla
    ancha. La fuente del teléfono solo se usa ahí; las demás, en cualquier ancho."""
    if not ancho or not alto:
        return "100vw"
    proporcion = ancho / alto
    telefono = _pintada(proporcion, ASOMO_PHONE)
    if solo_telefono:
        return telefono
    return f"{PORTADA_TELEFONO} {telefono}, {_pintada(proporcion, ASOMO)}"


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
        return ", ".join(f"{static(lamina_path(forma, w, ext))} {w}w" for w, _ in LAMINA[forma])

    formats = [ext for ext, _, _ in MediaAsset.PORTADA_FORMATS]
    (ancho_alta, alto_alta), (ancho, alto) = LAMINA["alta"][-1], LAMINA["ancha"][-1]
    fuentes = [
        _fuente(PORTADA_TELEFONO, ext, srcset("alta", ext), ancho_alta, alto_alta)
        for ext in formats
    ] + [_fuente("", ext, srcset("ancha", ext), ancho, alto) for ext in formats]
    return {
        "fuentes": fuentes,
        "src": static(lamina_path(*LAMINA_FALLBACK)),
        "srcset": "",
        "sizes": "",
        "width": ancho,
        "height": alto,
        "alt": "",
    }


@register.inclusion_tag("site/partials/_portada_img.html")
def portada_img(imagen=None, telefono=None):
    """La obra de la portada: un <picture> con AVIF y WebP, el recorte vertical para el
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
