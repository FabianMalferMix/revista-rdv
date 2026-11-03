"""Redacción de los tokens del boletín, que viajan en la URL.

Los enlaces de confirmación y baja del boletín llevan el token en la RUTA
(`/novedades/confirmar/<token>/`, `/novedades/baja/<token>/`). Quien lea un registro que
contenga una de esas rutas puede dar de baja una suscripción ajena. Aquí se redacta el token
en dos salidas de Python:

- el logging: `RedactTokensFilter`, en el handler de consola, reescribe el mensaje ya
  formateado, y `JsonFormatter` (config/logformat.py) redacta además cada campo;
- Sentry: `sentry_before_send` redacta la URL, la query y el nombre de la transacción de
  cada evento, y `sentry_before_breadcrumb`, las migas de pan.

Las rutas con token no se copian aquí: el patrón se construye con `reverse()` sobre toda
ruta del URLconf que reciba un `token`, así que renombrar una o añadir otra no deja su
token en claro. Los logs de acceso y de errores del borde los escribe Caddy, que redacta
con su propio filtro (`infra/caddy/Caddyfile`); una prueba compara ese filtro con estas
rutas.
"""

import re

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


def sentry_before_send(event, hint):
    """Redacta los tokens antes de que el evento salga hacia Sentry."""
    try:
        request = event.get("request")
        if isinstance(request, dict):
            if "url" in request:
                request["url"] = redact_path(request["url"])
            if "query_string" in request:
                request["query_string"] = redact_path(request["query_string"])
        if isinstance(event.get("transaction"), str):
            event["transaction"] = redact_path(event["transaction"])
    except Exception:  # noqa: BLE001 - jamás debe impedir el reporte de un error
        pass
    return event


def sentry_before_breadcrumb(crumb, hint):
    """Misma redacción para las migas de pan (registran cada petición)."""
    try:
        datos = crumb.get("data")
        if isinstance(datos, dict) and isinstance(datos.get("url"), str):
            datos["url"] = redact_path(datos["url"])
        if isinstance(crumb.get("message"), str):
            crumb["message"] = redact_path(crumb["message"])
    except Exception:  # noqa: BLE001
        pass
    return crumb


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
