"""Caché Redis que degrada en vez de romper (hallazgo S-22).

`django_ratelimit.core` llama a `cache.add()` y `cache.incr()` sin proteger la llamada:
solo captura `socket.gaierror` (fallo de DNS) y `ValueError`. Con Redis caído o
rechazando escrituras, `redis.exceptions.ConnectionError` subía hasta la vista y los
formularios públicos de newsletter y envíos —y ahora también el buscador— devolvían un
HTTP 500.

La librería SÍ tiene una ruta de degradación diseñada: si el contador acaba en `None`,
aplica `RATELIMIT_FAIL_OPEN` (por defecto: fail-closed, es decir, limita). Este backend
se limita a traducir los fallos de Redis al lenguaje que esa ruta ya entiende, en vez
de reimplementar la política:

  · `add()`  → False   (la librería pasa a intentar `incr`)
  · `incr()` → ValueError  (la librería lo captura y deja el contador en None)
  · `get()`  → el valor por defecto

Consecuencia deliberada: con Redis caído los endpoints con rate limit responden «espera
un momento» en lugar de un 500. Se prefiere fail-closed porque quedarse sin control
anti-abuso es peor que perder temporalmente el envío de un formulario; y con Redis caído
el sitio ya está degradado de todos modos (Celery tampoco puede encolar).
"""

import functools
import logging
import time

import redis
from django.core.cache.backends.redis import RedisCache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# Con Redis caído, cada visita falla en varias operaciones: un ERROR con su traza (que llega a
# Sentry) por cada intervalo, y el resto, un WARNING de una línea.
ERROR_INTERVAL = 300  # segundos
_last_error = None


def _degraded(operation):
    global _last_error
    now = time.monotonic()
    if _last_error is None or now - _last_error >= ERROR_INTERVAL:
        _last_error = now
        logger.error("Caché Redis no disponible en %s(); se degrada", operation, exc_info=True)
    else:
        logger.warning("Caché Redis no disponible en %s(); se degrada", operation)


# Lo que devuelve cada método de RedisCache cuando Redis no responde: lo mismo que una caché
# vacía o que no pudo escribir. `incr` lanza ValueError, que es lo que django-ratelimit espera
# cuando no se puede contar. Los demás métodos públicos de BaseCache (decr, get_or_set, las
# versiones asíncronas…) delegan en estos.
def _cannot_count(*args, **kwargs):
    raise ValueError("caché no disponible")


FALLBACKS = {
    "add": lambda *args, **kwargs: False,
    "clear": lambda *args, **kwargs: None,
    "delete": lambda *args, **kwargs: False,
    "delete_many": lambda *args, **kwargs: None,
    "get": lambda key, default=None, version=None: default,
    "get_many": lambda *args, **kwargs: {},
    "has_key": lambda *args, **kwargs: False,
    "incr": _cannot_count,
    "set": lambda *args, **kwargs: False,
    "set_many": lambda data, *args, **kwargs: list(data),
    "touch": lambda *args, **kwargs: False,
}
# Métodos públicos de RedisCache que no hablan con Redis.
WITHOUT_REDIS = {"get_backend_timeout"}


def _resilient(name, method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except RedisError:
            _degraded(name)
            return FALLBACKS[name](*args, **kwargs)

    return wrapper


class ResilientRedisCache(RedisCache):
    """RedisCache que no propaga los errores de Redis: cada método público degrada a lo que
    devolvería una caché vacía (tests/test_resilience.py compara la lista con RedisCache)."""


for _name in FALLBACKS:
    setattr(ResilientRedisCache, _name, _resilient(_name, getattr(RedisCache, _name)))


# Lo que leen las vistas con límite de tasa cuando la caché no puede contar: el límite falla
# cerrado, pero el mensaje no puede decir «demasiados intentos».
SERVICE_UNAVAILABLE = "El servicio no está disponible en este momento. Prueba en unos minutos."


def cache_ping():
    """None si la caché de Redis responde (o si la caché no es Redis); si no, la causa."""
    from django.conf import settings

    cache = settings.CACHES["default"]
    location = str(cache.get("LOCATION", ""))
    if not location.startswith(("redis://", "rediss://")):
        return None  # LocMem en desarrollo y en las pruebas
    try:
        redis.from_url(location, socket_connect_timeout=1, socket_timeout=1).ping()
    except RedisError as exc:
        return str(exc)
    return None


def counters_available():
    """Lo preguntan las vistas al quedar limitadas: ¿cuenta la caché, o está caída?"""
    return cache_ping() is None
