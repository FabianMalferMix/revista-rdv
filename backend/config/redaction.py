"""Redacción de los tokens del boletín, que viajan en la URL.

Los enlaces de confirmación y baja del boletín llevan el token en la RUTA:

    /novedades/confirmar/<token>/
    /novedades/baja/<token>/

Quien lea un registro que contenga una de esas rutas puede dar de baja una suscripción
ajena. Aquí se redacta el token en dos salidas de Python:

- el logging: `RedactTokensFilter`, en el handler de consola, reescribe el mensaje ya
  formateado;
- Sentry: `sentry_before_send` redacta la URL, la query y el nombre de la transacción de
  cada evento, y `sentry_before_breadcrumb`, las migas de pan.

Lo demás que Sentry adjunta a un evento (cabeceras como `Referer`, variables locales,
textos de excepción) no pasa por esta redacción. Los logs de acceso y de errores del
borde los escribe Caddy, que redacta la ruta con su propio filtro
(`infra/caddy/Caddyfile`); gunicorn no escribe log de acceso.
"""

import re

# Rutas cuyo último segmento es un secreto.
_RUTA_CON_TOKEN = re.compile(r"(/novedades/(?:confirmar|baja))/[^/]+/?")
_REDACTADO = r"\1/<redactado>/"


def redact_path(value):
    """Sustituye el token de las rutas del boletín por un marcador."""
    if not value or not isinstance(value, str):
        return value
    return _RUTA_CON_TOKEN.sub(_REDACTADO, value)


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
