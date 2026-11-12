"""La caché del sitemap y de los feeds: una hora, o hasta que cambie algo de lo que listan.

Cada respuesta se guarda con `cache_page` bajo una clave que lleva la generación vigente, un
número que vive en la misma caché: la hora, en nanosegundos, del último cambio. Guardar o borrar
una pieza de las que listan abre una generación nueva (`bump_generation`, desde
apps/site/signals.py, cuando el cambio ya está confirmado): lo guardado con la anterior ya no se
pide y caduca solo. La caché nunca se vacía entera, porque en Redis guarda también los contadores
del límite de tasa.

Quien la lee tiene que revalidar cada vez (`max-age=0, no-cache`), así que nadie guarda fuera de
aquí una lista con una pieza ya retirada; si nada cambió, recibe un 304 sin cuerpo
(ConditionalGetMiddleware). `Last-Modified` es la hora de la generación: la del feed sería la de
su ítem más reciente, que no se mueve al retirar otro.
"""

import functools
from time import time_ns

from django.conf import settings
from django.core.cache import cache
from django.utils.cache import patch_cache_control
from django.utils.http import http_date
from django.views.decorators.cache import cache_page

TIMEOUT = 60 * 60
GENERATION_KEY = "listing-cache:generation"


def _new_generation(previous=None):
    # Mayor que la anterior aunque el reloj no avance: repetir un número ya usado serviría lo
    # guardado antes del cambio.
    now = time_ns()
    return max(now, previous + 1) if previous else now


def current_generation():
    """La generación vigente, o None si la caché no responde."""
    generation = cache.get(GENERATION_KEY)
    if generation is None:
        cache.add(GENERATION_KEY, _new_generation(), timeout=None)
        generation = cache.get(GENERATION_KEY)
    return generation


def bump_generation():
    # Dos cambios a la vez abren dos generaciones; manda la última que se escribe, y las dos son
    # nuevas. Si la caché no responde en ese momento, la generación no cambia (config/cache.py
    # lo registra): al volver, lo guardado antes del cambio se sirve hasta que caduca.
    cache.set(GENERATION_KEY, _new_generation(cache.get(GENERATION_KEY)), timeout=None)


def _for_readers(generation):
    """Lo que dicen las cabeceras a quien lee: que vuelva a preguntar cada vez (no-cache), y la
    hora de la generación. Va encima de lo que guarda `cache_page`, que no guarda una respuesta
    con `no-cache`."""

    def patch(response):
        patch_cache_control(response, max_age=0, no_cache=True)
        response.headers["Expires"] = http_date()
        response.headers["Last-Modified"] = http_date(generation // 10**9 if generation else None)
        return response

    return patch


def cached_listing(view):
    """Envuelve la vista del sitemap o de un feed en la caché de la generación vigente.

    No se guarda lo que lleva parámetros (cada combinación sería otra clave), ni en desarrollo,
    donde la caché es de cada proceso y no la vaciaría lo que guarda un comando o el worker.
    `functools.wraps` deja llegar a la vista envuelta (`inspect.unwrap`)."""

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        generation = None if settings.DEBUG else current_generation()
        if generation is None or request.GET:
            response = view(request, *args, **kwargs)
        else:
            cached = cache_page(TIMEOUT, key_prefix=f"listing-cache.{generation}")(view)
            response = cached(request, *args, **kwargs)
        patch = _for_readers(generation)
        if hasattr(response, "add_post_render_callback"):
            # El sitemap es una TemplateResponse: se pinta al salir de aquí y `cache_page` lo
            # guarda al pintarse, así que las cabeceras van después. La que sale de la caché ya
            # está pintada y las recibe en el acto.
            response.add_post_render_callback(patch)
        else:
            patch(response)
        return response

    return wrapper
