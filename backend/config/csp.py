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

# Directivas fijas. `script-src` se completa por petición con el nonce (abajo).
_DIRECTIVES = (
    ("default-src", "'self'"),
    ("script-src", None),  # marcador: se rellena con 'self' [+ nonce]
    ("style-src", "'self' 'unsafe-inline'"),
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


def _new_nonce():
    return base64.b64encode(os.urandom(16)).decode("ascii")


class ContentSecurityPolicyMiddleware:
    """Fija la cabecera CSP; genera el nonce solo si la plantilla lo usa."""

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

        # No pisar una CSP fijada aguas arriba (p. ej. por una vista concreta).
        if (
            "Content-Security-Policy" in response
            or "Content-Security-Policy-Report-Only" in response
        ):
            return response

        script_src = "'self'"
        if state["nonce"] is not None:
            script_src += f" 'nonce-{state['nonce']}'"

        parts = [f"{name} {script_src if value is None else value}" for name, value in _DIRECTIVES]
        response[self.header] = "; ".join(parts)
        return response
