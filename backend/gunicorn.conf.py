"""Configuración de gunicorn. La lee él solo: está en su directorio de trabajo (/app).

Es la única fuente de sus opciones. La imagen arranca `gunicorn config.wsgi:application` sin
más, y el compose de producción y el CI usan ese mismo comando: una opción escrita en otro
sitio dejaría de coincidir con lo que el CI prueba. gunicorn ignora en silencio un nombre que
no conoce; tests/test_gunicorn_config.py comprueba que todos los de aquí lo son, y los
auxiliares empiezan con «_».

Los logs de gunicorn (arranque, procesos, errores al atender una petición) salen en JSON y
con la redacción de los tokens, como los de Django: con su formato por defecto escribiría
texto plano entre las líneas JSON, y un error al atender una ruta con token la dejaría en
claro.
"""

from config.env import env_int as _env_int

bind = "0.0.0.0:8000"
# Con hilos, gunicorn usa la clase gthread en vez de sync: una petición lenta no bloquea un
# proceso entero, y con los valores por defecto atiende doce a la vez. Los plazos del borde
# están en infra/caddy/Caddyfile.
workers = _env_int("GUNICORN_WORKERS", 3)
threads = _env_int("GUNICORN_THREADS", 4)
# Con gthread, timeout no es un plazo por petición: el proceso sigue avisando que está vivo
# aunque todos sus hilos estén ocupados. El plazo de cada consulta lo pone statement_timeout
# (config/settings.py).
timeout = 30
# Al pararlo, las peticiones en curso tienen este plazo para terminar; Docker espera más
# antes de matar el proceso (stop_grace_period de web, en docker-compose.prod.yml).
graceful_timeout = 30
# Cada proceso se renueva tras unas mil peticiones, con un margen al azar para que no lo
# hagan todos a la vez: acota lo que pueda crecer su memoria.
max_requests = 1000
max_requests_jitter = 100
# A gunicorn solo llega Caddy, por la red interna del compose (web no se publica al host):
# se confía en sus cabeceras X-Forwarded-*.
forwarded_allow_ips = "*"
# Sin log de acceso: lo escribe Caddy, que redacta el token de la ruta. El formato de acceso
# de gunicorn no admite sustituciones.
accesslog = None

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
