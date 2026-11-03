"""Configuración de gunicorn. La lee él solo: está en su directorio de trabajo (/app).

Los logs de gunicorn (arranque, procesos, errores al atender una petición) salen en JSON y
con la redacción de los tokens, como los de Django. Con su formato por defecto escribía
texto plano entre las líneas JSON, y un error al atender una ruta con token la dejaba en
claro.
"""

logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "config.logformat.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stderr",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "gunicorn.error": {"level": "INFO", "handlers": ["error_console"], "propagate": False},
        "gunicorn.access": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}
