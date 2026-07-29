"""Degradación ante fallos de Redis y de SMTP (hallazgos S-22, S-23).

`django_ratelimit` llama a `cache.add()`/`cache.incr()` capturando solo `socket.gaierror`
y `ValueError`. Con Redis caído, `redis.exceptions.ConnectionError` subía hasta la vista
y los formularios públicos devolvían un HTTP 500 — justo cuando el sitio ya estaba
degradado.
"""

import pytest
from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse

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
        reverse("community:subscribe"), {"email": "alguien@example.com", "apodo": ""}
    )
    assert resp.status_code != 500
    assert resp.status_code in (200, 302)


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_el_buscador_no_da_500_con_redis_caido(client):
    resp = client.get(reverse("content:search"), {"q": "umbral"})
    assert resp.status_code == 200


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_el_envio_de_propuestas_no_da_500_con_redis_caido(client):
    resp = client.get(reverse("submissions:submit"))
    assert resp.status_code == 200


def test_la_politica_ante_cache_no_disponible_es_fail_closed(settings):
    """Explícita, no heredada: quedarse sin control anti-abuso es peor que rechazar
    temporalmente un envío."""
    assert settings.RATELIMIT_FAIL_OPEN is False


def test_hay_limites_de_tiempo_en_celery_y_en_el_correo(settings):
    """Sin ellos, un SMTP que acepta la conexión y luego calla inmovilizaba los slots
    del worker indefinidamente (S-23)."""
    assert settings.EMAIL_TIMEOUT > 0
    assert settings.CELERY_TASK_SOFT_TIME_LIMIT > 0
    assert settings.CELERY_TASK_TIME_LIMIT > settings.CELERY_TASK_SOFT_TIME_LIMIT
    # Con acks_late, una tarea que muere por time limit se reencola en vez de perderse.
    assert settings.CELERY_TASK_ACKS_LATE is True
    assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1
