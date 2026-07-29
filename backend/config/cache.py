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

import logging

from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)

try:  # pragma: no cover - redis siempre está instalado en este proyecto
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover
    RedisError = ()


class ResilientRedisCache(RedisCache):
    """RedisCache que no propaga los errores de conexión de Redis."""

    def add(self, *args, **kwargs):
        try:
            return super().add(*args, **kwargs)
        except RedisError:
            logger.warning("Caché Redis no disponible en add(); se degrada", exc_info=True)
            return False

    def incr(self, *args, **kwargs):
        try:
            return super().incr(*args, **kwargs)
        except RedisError as exc:
            # ValueError es justo lo que django-ratelimit espera cuando el backend no
            # puede contar (lo documenta para python3-memcached).
            logger.warning("Caché Redis no disponible en incr(); se degrada", exc_info=True)
            raise ValueError("caché no disponible") from exc

    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default, version)
        except RedisError:
            logger.warning("Caché Redis no disponible en get(); se degrada", exc_info=True)
            return default

    def set(self, *args, **kwargs):
        try:
            return super().set(*args, **kwargs)
        except RedisError:
            logger.warning("Caché Redis no disponible en set(); se degrada", exc_info=True)
            return False

    def delete(self, *args, **kwargs):
        try:
            return super().delete(*args, **kwargs)
        except RedisError:
            logger.warning("Caché Redis no disponible en delete(); se degrada", exc_info=True)
            return False
