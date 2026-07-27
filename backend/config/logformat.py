"""Formateador de logs a JSON (una línea por registro), sin dependencias externas.

Se usa en producción para que los logs sean agregables/consultables por un colector
(Loki, CloudWatch, etc.). En desarrollo se mantiene el texto plano legible.
"""

import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        # Campos extra pasados con logger.info(..., extra={...}).
        standard = logging.LogRecord("", 0, "", 0, "", (), None).__dict__
        for key, value in record.__dict__.items():
            if key not in standard and key not in ("message", "asctime"):
                data[key] = value
        return json.dumps(data, ensure_ascii=False, default=str)
