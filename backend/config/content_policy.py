"""La política del contenido que entra de fuera: qué reproductores se incrustan y qué HTML de autor
se publica.

Cada regla está escrita aquí una sola vez y las demás capas la leen: la CSP arma `frame-src` con los
orígenes de los reproductores (`config/csp.py`), el filtro `embed_src` arma con ellos el reproductor
de un registro, el panel nombra a los proveedores en la ayuda de los registros, nh3 sanea el HTML de
autor con estas listas (`apps/content/sanitize.py`) y el editor del panel, TinyMCE, recibe las mismas
en un atributo de su cuadro de texto (`RichTextWidget`).
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings

# ── Los reproductores incrustados ─────────────────────────────


@dataclass(frozen=True)
class EmbedProvider:
    """Un proveedor de video cuyo reproductor se incrusta en la ficha de un registro.

    `pattern` reconoce un enlace suyo y captura el identificador del video en el grupo `id`;
    `player` es la dirección del reproductor, con `{id}` donde va ese identificador. El origen de
    `player` es el que la CSP admite en `frame-src`.
    """

    name: str
    pattern: re.Pattern
    player: str

    @property
    def origin(self):
        parts = urlsplit(self.player)
        return f"{parts.scheme}://{parts.netloc}"

    def src(self, url):
        """La dirección del reproductor para ese enlace, o vacía si el enlace no es suyo."""
        match = self.pattern.search(url or "")
        return self.player.format(id=match["id"]) if match else ""


# En orden: el primero que reconoce un enlace es su proveedor.
EMBED_PROVIDERS = (
    EmbedProvider(
        "YouTube",
        re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)(?P<id>[\w-]{6,})"),
        "https://www.youtube-nocookie.com/embed/{id}",
    ),
    EmbedProvider(
        "Vimeo",
        re.compile(r"vimeo\.com/(?P<id>\d+)"),
        "https://player.vimeo.com/video/{id}",
    ),
)


def embed_provider_for(url):
    """El proveedor que reconoce ese enlace, o None."""
    return next((p for p in EMBED_PROVIDERS if url and p.pattern.search(url)), None)


def embed_provider_names():
    """Los proveedores como se nombran en una frase: «YouTube o Vimeo»."""
    *others, last = [provider.name for provider in EMBED_PROVIDERS]
    return f"{', '.join(others)} o {last}" if others else last


# ── El HTML de autor ──────────────────────────────────────────
# El cuerpo de los textos y de las páginas. Lo que no está en estas listas lo quita nh3 al guardar
# y al mostrar, y el editor del panel no lo deja escribir.

ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "hr",
        "blockquote",
        "pre",
        "code",
        "em",
        "strong",
        "i",
        "b",
        "u",
        "s",
        "sub",
        "sup",
        "small",
        "cite",
        "h2",
        "h3",
        "h4",
        "ul",
        "ol",
        "li",
        "a",
        "img",
        "figure",
        "figcaption",
    }
)

# Los atributos de cada etiqueta. «*» son los de todas: ninguno. Hay que decirlo, porque sin «*»
# nh3 admite en todas `lang` y `title`, que el editor del panel no deja escribir.
ALLOWED_ATTRIBUTES = {
    "*": frozenset(),
    "a": frozenset({"href", "title"}),
    "img": frozenset({"src", "alt", "title", "width", "height", "loading"}),
}

# Los esquemas admitidos en href y src, fijados a mano: nh3 admite por defecto 25 (ssh, magnet,
# bitcoin, sms, wtai…) que este sitio no necesita y que podrían cambiar con una versión de la
# librería. Los peligrosos (javascript:, data:, vbscript:) ya los descartaba nh3.
ALLOWED_URL_SCHEMES = frozenset({"http", "https", "mailto"})

# Las imágenes del HTML de autor solo se publican si son del propio sitio (`is_own_url`): la CSP
# (`img-src 'self'`) bloquea las de fuera, que saldrían rotas, y pedirlas le contaría a ese otro
# sitio cada visita. Lo dice el panel junto al cuerpo.
AUTHORED_HTML_HELP = (
    "Las imágenes de otros sitios no se publican: al guardar, el texto se queda solo con las de "
    "este sitio."
)

# Lo que el navegador quita o lee de otra manera al leer una dirección (el estándar URL de WHATWG):
# los blancos y los caracteres de control de los extremos, los tabuladores y saltos de línea de
# dentro, y en http(s) «\» vale por «/». Se hace lo mismo antes de mirar de quién es una dirección,
# para que « https://otro/», «ht\ttps://otro/» o «/\otro/» no pasen por propias.
_C0_CONTROL_OR_SPACE = "".join(map(chr, range(0x21)))
_TAB_OR_NEWLINE = re.compile(r"[\t\n\r]")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _origin(parts):
    return parts.scheme, parts.hostname, parts.port or _DEFAULT_PORTS.get(parts.scheme)


def is_own_url(url):
    """Si una dirección del HTML de autor es del propio sitio: una ruta relativa o una dirección con
    el origen de SITE_URL. Ante la duda, no lo es."""
    url = _TAB_OR_NEWLINE.sub("", url).strip(_C0_CONTROL_OR_SPACE).replace("\\", "/")
    # «//otro/…» (y «///otro/…», que el navegador lee igual) es de otro sitio aunque no diga esquema.
    if not url or url.startswith("//"):
        return False
    try:
        parts = urlsplit(url)
        if not parts.scheme and not parts.netloc:
            return True
        return bool(parts.netloc) and _origin(parts) == _origin(urlsplit(settings.SITE_URL))
    except ValueError:  # un puerto que no es un número, un IPv6 mal cerrado
        return False
