"""Content-Security-Policy con nonce por petición.

Sin dependencias externas: una CSP restrictiva declarada en un único lugar y
aplicada a todas las respuestas dinámicas. El único script inline propio (JSON-LD
en el detalle de artículo) lleva el nonce; el resto del JS (htmx, TinyMCE, admin)
va auto-hospedado y entra por 'self'. Los estilos permiten 'unsafe-inline' porque
el admin de Django y TinyMCE inyectan estilos en línea; el riesgo de XSS por estilo
es bajo y el saneo nh3 ya recorta el HTML autoral.

Con DJANGO_CSP_REPORT_ONLY=1 se emite en modo Report-Only (observa violaciones sin
bloquear), útil como red de seguridad antes de forzar la política en producción.
"""

import base64
import os

from django.conf import settings
from django.utils.functional import SimpleLazyObject

# Marcador interno para la directiva que depende de la ruta.
_STYLE_MARKER = object()

# El admin de Django y TinyMCE inyectan estilos en línea y no hay forma de ponerles un
# nonce. El SITIO PÚBLICO, en cambio, no tiene ni un solo atributo `style=` ni un bloque
# <style> —el CSS propio va en un fichero estático, y el saneo nh3 descarta el atributo
# `style` del HTML autoral—, así que ahí no hace falta relajar nada. Emitir
# 'unsafe-inline' solo bajo /admin/ reduce lo que un XSS podría hacer en las páginas que
# ve el público (superposiciones de secuestro de clic, exfiltración por selectores CSS).
_STYLE_PUBLICO = "'self'"
_STYLE_ADMIN = "'self' 'unsafe-inline'"

# Directivas fijas. `script-src` y `style-src` se completan por petición (abajo).
_DIRECTIVES = (
    ("default-src", "'self'"),
    ("script-src", None),  # marcador: se rellena con 'self' [+ nonce]
    ("style-src", _STYLE_MARKER),  # marcador: 'unsafe-inline' solo bajo /admin/
    ("img-src", "'self' data:"),
    ("font-src", "'self' data:"),
    ("connect-src", "'self'"),
    # 'self' es necesario para el iframe de edición de TinyMCE (admin); los otros
    # dos, para los reproductores embebidos de registros.
    ("frame-src", "'self' https://www.youtube-nocookie.com https://player.vimeo.com"),
    ("media-src", "'self'"),
    ("object-src", "'none'"),
    ("base-uri", "'self'"),
    ("form-action", "'self'"),
    ("frame-ancestors", "'none'"),
)


# El sitio no usa estas APIs del navegador; se deniegan explícitamente (defensa en
# profundidad, y bloquea que un embed las solicite en nombre de la página).
_PERMISSIONS_POLICY = "geolocation=(), camera=(), microphone=(), payment=()"


def _new_nonce():
    return base64.b64encode(os.urandom(16)).decode("ascii")


class ContentSecurityPolicyMiddleware:
    """Fija la cabecera CSP; genera el nonce solo si la plantilla lo usa.

    POR QUÉ VA DESPUÉS DE WhiteNoise (y no antes): así los estáticos no llevan CSP. Se
    evaluó moverlo delante para cubrirlos y NO compensa — los navegadores ignoran la CSP
    en subrecursos (hoja de estilos, script, imagen): solo la aplican a documentos. El
    único caso con valor sería navegar directamente a un documento servido desde
    STATIC_ROOT, y ahí no hay ninguno: el árbol de estáticos son .js, .css, .md y .txt.
    A cambio, moverlo añadiría una cabecera a cada petición de estático (TinyMCE solo ya
    son 14 archivos). `tests/test_security_csp.py` fija esa suposición: si alguien añade
    un .html o .svg a los estáticos, el test avisa para reconsiderarlo.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.report_only = getattr(settings, "CSP_REPORT_ONLY", False)
        self.header = (
            "Content-Security-Policy-Report-Only" if self.report_only else "Content-Security-Policy"
        )

    def __call__(self, request):
        state = {"nonce": None}

        def nonce():
            if state["nonce"] is None:
                state["nonce"] = _new_nonce()
            return state["nonce"]

        # SimpleLazyObject: el nonce solo se materializa si la plantilla lo usa.
        request.csp_nonce = SimpleLazyObject(nonce)
        response = self.get_response(request)

        # Permissions-Policy restrictiva en todas las respuestas (setdefault: una vista
        # concreta puede fijar la suya). Se hace antes del posible early-return del CSP.
        response.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)

        # No pisar una CSP fijada aguas arriba (p. ej. por una vista concreta).
        if (
            "Content-Security-Policy" in response
            or "Content-Security-Policy-Report-Only" in response
        ):
            return response

        script_src = "'self'"
        if state["nonce"] is not None:
            script_src += f" 'nonce-{state['nonce']}'"

        # El panel necesita estilos en línea; el sitio público no (ver arriba).
        style_src = _STYLE_ADMIN if request.path.startswith("/admin/") else _STYLE_PUBLICO

        parts = []
        for name, value in _DIRECTIVES:
            if value is None:
                value = script_src
            elif value is _STYLE_MARKER:
                value = style_src
            parts.append(f"{name} {value}")
        response[self.header] = "; ".join(parts)
        return response
