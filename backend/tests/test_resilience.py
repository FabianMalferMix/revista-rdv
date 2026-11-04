"""Degradación ante fallos de Redis y de SMTP (hallazgos S-22, S-23).

`django_ratelimit` llama a `cache.add()`/`cache.incr()` capturando solo `socket.gaierror`
y `ValueError`. Con Redis caído, `redis.exceptions.ConnectionError` subía hasta la vista
y los formularios públicos devolvían un HTTP 500 — justo cuando el sitio ya estaba
degradado.
"""

import pytest
from django.core.cache import caches
from django.core.cache.backends.redis import RedisCache
from django.test import override_settings
from django.urls import reverse

from config.cache import FALLBACKS, SERVICE_UNAVAILABLE, WITHOUT_REDIS

# Puerto sin nadie escuchando: simula Redis caído sin tocar el de verdad.
CACHE_CAIDA = {
    "default": {
        "BACKEND": "config.cache.ResilientRedisCache",
        "LOCATION": "redis://127.0.0.1:6399/0",
    }
}


@override_settings(CACHES=CACHE_CAIDA)
def test_la_cache_degrada_en_vez_de_propagar_el_error():
    cache = caches.create_connection("default")
    assert cache.add("k", 1, 60) is False
    assert cache.get("k") is None
    assert cache.get("k", "por-defecto") == "por-defecto"
    assert cache.set("k", 1, 60) is False
    assert cache.delete("k") is False


@override_settings(CACHES=CACHE_CAIDA)
def test_incr_se_traduce_a_valueerror():
    """`ValueError` es justo lo que django-ratelimit espera cuando el backend no puede
    contar: así entra en su ruta de degradación en vez de reventar."""
    cache = caches.create_connection("default")
    with pytest.raises(ValueError):
        cache.incr("k")


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_el_alta_de_newsletter_no_da_500_con_redis_caido(client):
    resp = client.post(
        reverse("community:subscribe"), {"email": "alguien@example.com", "apodo": ""}, follow=True
    )
    assert resp.status_code == 200
    # El límite falla cerrado, y lo dice con la verdad: no fueron demasiados intentos.
    assert SERVICE_UNAVAILABLE in resp.content.decode()


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_el_buscador_no_da_500_con_redis_caido(client):
    resp = client.get(reverse("content:search"), {"q": "umbral"})
    assert resp.status_code == 200
    assert SERVICE_UNAVAILABLE in resp.content.decode()


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_the_search_panel_announces_that_the_service_is_down(client):
    """El aviso llega también a la región de estado de la lupa, que es lo que oye el lector."""
    from bs4 import BeautifulSoup

    resp = client.get(reverse("content:search"), {"q": "umbral"}, headers={"HX-Request": "true"})
    assert resp.status_code == 200
    estado = BeautifulSoup(resp.content, "html.parser").select_one("#search-status")
    assert estado.get_text() == SERVICE_UNAVAILABLE


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_el_envio_de_propuestas_no_da_500_con_redis_caido(client):
    data = {
        "author_name": "Ana",
        "author_email": "ana@example.com",
        "type": "poesia",
        "title": "Un título",
        "body": "Unos versos",
    }
    resp = client.post(reverse("submissions:submit"), data)
    assert resp.status_code == 200
    assert SERVICE_UNAVAILABLE in resp.content.decode()


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=True)
def test_a_real_rate_limit_still_says_too_many_attempts(client):
    """Control positivo: con la caché en pie, pasarse del límite es «demasiados intentos»."""
    for i in range(6):
        resp = client.post(
            reverse("community:subscribe"), {"email": f"a{i}@example.com", "apodo": ""}, follow=True
        )
    html = resp.content.decode()
    assert "Demasiados intentos" in html
    assert SERVICE_UNAVAILABLE not in html


def test_the_wrapper_covers_every_redis_method():
    """Un método nuevo de RedisCache tiene que decidir qué devuelve con Redis caído."""
    own = {
        name
        for name, value in vars(RedisCache).items()
        if callable(value) and not name.startswith("_")
    }
    assert own == set(FALLBACKS) | WITHOUT_REDIS


@override_settings(CACHES=CACHE_CAIDA)
def test_every_method_degrades_with_redis_down():
    cache = caches["default"]
    assert cache.get_many(["a", "b"]) == {}
    assert cache.has_key("a") is False
    assert cache.touch("a") is False
    assert cache.set_many({"a": 1, "b": 2}) == ["a", "b"]
    cache.delete_many(["a"])
    cache.clear()
    assert cache.get_or_set("a", "por defecto") == "por defecto"
    with pytest.raises(ValueError):
        cache.decr("a")


def test_la_politica_ante_cache_no_disponible_es_fail_closed(settings):
    """Explícita, no heredada: quedarse sin control anti-abuso es peor que rechazar
    temporalmente un envío."""
    assert settings.RATELIMIT_FAIL_OPEN is False


def test_hay_limites_de_tiempo_en_celery_y_en_el_correo(settings):
    """Sin ellos, un SMTP que acepta la conexión y luego calla ocupa los procesos del
    worker indefinidamente."""
    assert settings.EMAIL_TIMEOUT > 0
    assert settings.CELERY_TASK_SOFT_TIME_LIMIT > 0
    # Un servidor que calla tiene que fallar por el socket antes que por el límite blando.
    assert settings.EMAIL_TIMEOUT < settings.CELERY_TASK_SOFT_TIME_LIMIT
    assert settings.CELERY_TASK_TIME_LIMIT > settings.CELERY_TASK_SOFT_TIME_LIMIT
    assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1


def test_a_task_that_times_out_is_not_requeued():
    """acks_late solo cubre la caída del worker entero. Una tarea que falla, agota su
    límite de tiempo o pierde su proceso se confirma igual y no se reencola: es lo que
    explica el comentario de settings.py, y si cambia esta configuración, cambia él."""
    from config.celery import app

    assert app.conf.task_acks_late is True
    assert app.conf.task_acks_on_failure_or_timeout is True
    assert not app.conf.task_reject_on_worker_lost
