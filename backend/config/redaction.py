"""Redacción de los tokens del boletín, que viajan en la URL.

Los enlaces de confirmación y baja del boletín llevan el token en la RUTA
(`/novedades/confirmar/<token>/`, `/novedades/baja/<token>/`). Quien lea un registro que
contenga una de esas rutas puede dar de baja una suscripción ajena. Aquí se redacta el token
en dos salidas de Python:

- el logging: `RedactTokensFilter`, en el handler de consola, reescribe el mensaje ya
  formateado, y `JsonFormatter` (config/logformat.py) redacta además cada campo, también las
  direcciones de correo;
- Sentry: `sentry_before_send` y `sentry_before_breadcrumb` redactan los tokens y las
  direcciones de correo de todo el evento y de cada miga (config/sentry.py).

Las rutas con token no se copian aquí: el patrón se construye con `reverse()` sobre toda
ruta del URLconf que reciba un `token`, así que renombrar una o añadir otra no deja su
token en claro. Los logs de acceso y de errores del borde los escribe Caddy, que redacta
con su propio filtro (`infra/caddy/Caddyfile`); una prueba compara ese filtro con estas
rutas.
"""

import re

from sentry_sdk.scrubber import DEFAULT_DENYLIST

_REDACTADO = r"\1/<redactado>/"
# Lo que se escribe en lugar del texto si el patrón no se puede construir con Django ya
# en marcha: sin patrón no se sabe qué redactar, y se falla cerrado.
SIN_PATRON = "<redactado: no se pudo construir el patrón de las rutas con token>"
_patterns = {}


def token_route_prefixes():
    """El comienzo de cada ruta del URLconf que lleva un token: «/novedades/baja/», …"""
    from django.urls import URLResolver, get_resolver, reverse

    prefixes = []

    def walk(patterns, namespace):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                inner = ":".join(filter(None, [namespace, pattern.namespace]))
                walk(pattern.url_patterns, inner)
            elif "token" in getattr(pattern.pattern, "converters", {}):
                name = f"{namespace}:{pattern.name}" if namespace else pattern.name
                url = reverse(name, kwargs={"token": "TOKEN"})
                prefixes.append(url[: url.index("TOKEN")])

    walk(get_resolver().url_patterns, None)
    return prefixes


def _token_route_pattern():
    """El patrón de las rutas con token, o None antes de que Django arranque.

    Antes de `django.setup()` el URLconf no se puede resolver, y tampoco hace falta: aún no
    se atiende ninguna petición ni tarea, así que no hay rutas con token que redactar.
    """
    from django.apps import apps
    from django.conf import settings

    if not apps.ready:
        return None
    key = settings.ROOT_URLCONF
    if key not in _patterns:
        prefixes = [re.escape(prefix.rstrip("/")) for prefix in token_route_prefixes()]
        _patterns[key] = re.compile(rf"({'|'.join(prefixes)})/[^/]+/?") if prefixes else None
    return _patterns[key]


def redact_path(value):
    """Sustituye el token de las rutas del boletín por un marcador."""
    if not value or not isinstance(value, str):
        return value
    try:
        pattern = _token_route_pattern()
    except Exception:  # noqa: BLE001 - sin patrón no se sabe qué ocultar: se oculta todo
        return SIN_PATRON
    return pattern.sub(_REDACTADO, value) if pattern else value


# Claves cuyo valor no sale hacia Sentry, a cualquier profundidad del evento: las que el SDK
# considera sensibles (contraseñas, tokens, cookies…) y las que aquí llevan datos de una
# persona o un secreto: el correo y el nombre de quien se suscribe o envía un texto, el texto
# mismo y las URL del boletín, que llevan el token.
SENSITIVE_KEYS = frozenset(key.lower() for key in DEFAULT_DENYLIST) | {
    "email",
    "author_email",
    "author_name",
    "body",
    "title",
    "confirm_url",
    "unsub_url",
    "next",
    "sub",
    "confirm_token",
}
FILTERED = "[Filtered]"
# Una dirección de correo dentro de cualquier texto: el mensaje de un error SMTP la cita.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
EMAIL_MARK = "<correo>"


def redact_text(value):
    """Sustituye los tokens de las rutas del boletín y las direcciones de correo.

    Es la redacción de todo texto que sale hacia el log JSON o hacia Sentry: cuando el servidor
    de correo rechaza un destinatario, la excepción lo cita, y Celery la copia en el mensaje, en
    la traza y en los extras de la línea de error de la tarea.
    """
    if not value or not isinstance(value, str):
        return value
    return _EMAIL.sub(EMAIL_MARK, redact_path(value))


# Cabeceras que repiten la URL de la página, y con ella el token.
_URL_HEADERS = {"referer", "hx-current-url"}


def _scrub(value):
    """Redacta los tokens y las direcciones de correo de todas las cadenas, y el valor de las
    claves sensibles, a cualquier profundidad."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            key: FILTERED if str(key).lower() in SENSITIVE_KEYS else _scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(item) for item in value]
    return value


def sentry_before_send(event, hint):
    """Limpia el evento antes de que salga hacia Sentry; si algo falla, no lo envía.

    Quita el cuerpo de la petición y las cabeceras que repiten la URL de la página, y
    redacta los tokens y las direcciones de correo del resto: mensaje, excepciones,
    transacción, migas y extras.
    """
    try:
        request = event.get("request")
        if isinstance(request, dict):
            request.pop("data", None)
            headers = request.get("headers")
            if isinstance(headers, dict):
                for name in [n for n in headers if str(n).lower() in _URL_HEADERS]:
                    del headers[name]
        return _scrub(event)
    except Exception:  # noqa: BLE001 - un evento que no se pudo limpiar no sale
        return None


def sentry_before_breadcrumb(crumb, hint):
    """Misma limpieza para las migas de pan (registran cada petición y cada log)."""
    try:
        return _scrub(crumb)
    except Exception:  # noqa: BLE001
        return None


class RedactTokensFilter:
    """Filtro de logging que redacta los tokens del mensaje ya formateado.

    Se declara como clase (y no como función) para poder referenciarlo desde el dict de
    LOGGING con `()`.
    """

    def filter(self, record):
        try:
            mensaje = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        redactado = redact_path(mensaje)
        if redactado != mensaje:
            record.msg = redactado
            record.args = ()
        return True
