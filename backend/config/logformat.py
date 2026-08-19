"""Formateador de logs a JSON (una línea por registro), sin dependencias externas.

Se usa en producción para que los logs sean agregables/consultables por un colector
(Loki, CloudWatch, etc.). En desarrollo se mantiene el texto plano legible.
"""

import json
import logging

from config.redaction import redact_path


def _serializa_redactado(obj):
    """`default` de json.dumps: pasa a texto y redacta de camino.

    Es la última barrera y la que faltaba. `django.request` adjunta el WSGIRequest
    ENTERO como campo extra, y su repr() lleva la ruta cruda —con el token del
    boletín— aunque el mensaje ya venga redactado por `RedactTokensFilter`, que solo
    alcanza `record.msg`. En un 404 sobre /novedades/baja/<token>/ el log quedaba así:

        "message": "Not Found: /novedades/baja/<redactado>/"      <- redactado
        "request": "<WSGIRequest: GET '/novedades/baja/TOKEN/'>"  <- en claro

    Solo afectaba a producción: en desarrollo el formateador es `plain`, que no emite
    los campos extra.
    """
    return redact_path(str(obj))


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            # Redactado también aquí, y no solo en el filtro: así la garantía no depende
            # de que quien añada un handler recuerde engancharle `redact_tokens`.
            "message": redact_path(record.getMessage()),
        }
        if record.exc_info:
            # Una traza puede citar la ruta (p. ej. en el marco de la vista).
            data["exc_info"] = redact_path(self.formatException(record.exc_info))
        # Campos extra pasados con logger.info(..., extra={...}).
        standard = logging.LogRecord("", 0, "", 0, "", (), None).__dict__
        for key, value in record.__dict__.items():
            if key not in standard and key not in ("message", "asctime"):
                data[key] = redact_path(value) if isinstance(value, str) else value
        return json.dumps(data, ensure_ascii=False, default=_serializa_redactado)
