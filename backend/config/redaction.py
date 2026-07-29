"""Redacción de secretos que viajan en la URL (hallazgo S-20).

Los enlaces de confirmación y baja del boletín llevan el token en la RUTA:

    /novedades/confirmar/<token>/
    /novedades/baja/<token>/

Una ruta acaba en sitios que no controlamos ni auditamos: el log de acceso de gunicorn,
el log JSON de `django.request`, la cabecera `Referer` si la página enlazase fuera y —lo
más serio— el nombre de la transacción y las trazas que se envían a Sentry, es decir a
un tercero. Quien lea cualquiera de esos registros puede dar de baja (o, antes de
sec-11, confirmar) suscripciones ajenas.

Se redacta en los dos puntos de salida que Python controla: el logging de Django y lo
que se envía a Sentry.

RESIDUO CONOCIDO: el log de acceso de **gunicorn** (`--access-logfile -`) sigue
escribiendo la ruta completa, porque lo emite su propio logger y no admite un formato
que redacte. Mitigarlo exige una de tres: mover el log de acceso al borde (Caddy) y
quitar el de gunicorn, sustituir el `logger-class` de gunicorn, o —solución de fondo—
sacar el secreto de la ruta y pasarlo en el cuerpo del POST. Queda anotado en el
informe de seguridad.
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
