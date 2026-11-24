"""Degradación ante fallos de Redis y de SMTP.

`django_ratelimit` llama a `cache.add()`/`cache.incr()` capturando solo `socket.gaierror`
y `ValueError`. Si la caché no degradara (config/cache.py), con Redis caído
`redis.exceptions.ConnectionError` subiría hasta la vista y los formularios públicos
devolverían un HTTP 500 — justo cuando el sitio ya está degradado.
"""

import json

import pytest
from django.core.cache import caches
from django.core.cache.backends.redis import RedisCache
from django.test import override_settings
from django.urls import reverse

from config import ratelimit
from config.cache import ERROR_INTERVAL, FALLBACKS, SERVICE_UNAVAILABLE, WITHOUT_REDIS
from tests.factories import SEARCH_PANEL_HEADERS

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
    # El límite falla cerrado, y lo dice con la verdad: no fueron demasiados intentos, sino que
    # el servicio no está disponible (un 503, que dice cuándo volver).
    assert resp.status_code == 503
    assert int(resp["Retry-After"]) > 0
    assert SERVICE_UNAVAILABLE in resp.content.decode()


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_el_buscador_no_da_500_con_redis_caido(client):
    resp = client.get(reverse("site:search"), {"q": "umbral"})
    assert resp.status_code == 503
    assert int(resp["Retry-After"]) > 0
    assert SERVICE_UNAVAILABLE in resp.content.decode()


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_the_search_panel_announces_that_the_service_is_down(client):
    """El aviso llega también a la región de estado de la lupa, que es lo que oye el lector."""
    from bs4 import BeautifulSoup

    resp = client.get(reverse("site:search"), {"q": "umbral"}, headers=SEARCH_PANEL_HEADERS)
    assert resp.status_code == 200
    estado = BeautifulSoup(resp.content, "html.parser").select_one("#search-status")
    assert estado.get_text() == SERVICE_UNAVAILABLE


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_el_envio_de_propuestas_no_da_500_con_redis_caido(client):
    """El límite falla cerrado: la propuesta no se guarda, el aviso dice la verdad y lo escrito
    vuelve al formulario para enviarlo más tarde."""
    from bs4 import BeautifulSoup

    from apps.submissions.models import Submission

    data = {
        "author_name": "Ana",
        "author_email": "ana@example.com",
        "type": "poesia",
        "title": "Un título",
        "body": "Unos versos",
    }
    resp = client.post(reverse("submissions:submit"), data)
    assert resp.status_code == 503
    assert int(resp["Retry-After"]) > 0
    assert SERVICE_UNAVAILABLE in resp.content.decode()
    form = BeautifulSoup(resp.content, "html.parser")
    assert form.select_one('input[name="title"]').get("value") == "Un título"  # control
    assert not Submission.objects.exists()


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=True)
def test_a_real_rate_limit_still_says_too_many_attempts(client, frozen_rate_limit_window):
    """Control positivo: con la caché en pie, pasarse del límite es «demasiados intentos»."""
    for i in range(6):
        resp = client.post(
            reverse("community:subscribe"), {"email": f"a{i}@example.com", "apodo": ""}, follow=True
        )
    html = resp.content.decode()
    assert "Demasiados intentos" in html
    assert SERVICE_UNAVAILABLE not in html


def _closure_reports(events):
    return [event for event in events if event.get("logger") == "config.ratelimit"]


@pytest.mark.django_db
@override_settings(CACHES=CACHE_CAIDA, RATELIMIT_ENABLE=True)
def test_sentry_hears_of_the_closed_views_once_per_interval_and_without_personal_data(
    sentry_events, client, monkeypatch
):
    """Sentry ignora el logger que anota cada 503 (django.request). Le llega un ERROR por
    intervalo, con el mismo texto venga de la vista que venga, y sin el correo del formulario,
    lo buscado ni la IP de quien los pidió."""
    monkeypatch.setattr(ratelimit._report_due, "last", None)
    email, term, ip = "ana.prueba@example.com", "umbralinedito", "203.0.113.7"

    def search():
        return client.get(reverse("site:search"), {"q": term}, REMOTE_ADDR=ip).status_code

    subscribe = client.post(
        reverse("community:subscribe"), {"email": email, "apodo": ""}, REMOTE_ADDR=ip
    ).status_code
    assert (subscribe, search()) == (503, 503), "control: las dos vistas cerraron"
    assert len(_closure_reports(sentry_events())) == 1, "un ERROR por intervalo, no por 503"
    ratelimit._report_due.last -= ERROR_INTERVAL
    assert search() == 503

    first, second = _closure_reports(sentry_events())
    assert first["level"] == "error"
    assert first["logentry"]["message"] == ratelimit.UNAVAILABLE_REPORT
    assert second["logentry"] == first["logentry"], "las dos caídas, en un mismo issue"
    sent = json.dumps(sentry_events())
    for personal in (email, term, ip):
        assert personal not in sent
    # Ni la clave de su contador, que es un hash de la IP con datos que se conocen. Control: el
    # evento cuenta lo que pasó antes, la caché que no respondió.
    crumbs = {crumb.get("category") for crumb in first["breadcrumbs"]["values"]}
    assert "config.cache" in crumbs
    assert ":rl:" not in sent


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=True)
def test_a_real_rate_limit_sends_nothing_to_sentry(
    sentry_events, client, monkeypatch, frozen_rate_limit_window
):
    """Pasarse del límite es cosa de quien pide, no una caída: no llega a Sentry."""
    monkeypatch.setattr(ratelimit._report_due, "last", None)
    for i in range(6):
        resp = client.post(reverse("community:subscribe"), {"email": f"a{i}@example.com"})
    assert resp.status_code == 429, "control: el límite llegó"
    assert _closure_reports(sentry_events()) == []


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
    from apps.community.tasks import send_confirmation_email

    assert settings.EMAIL_TIMEOUT > 0
    assert settings.CELERY_TASK_SOFT_TIME_LIMIT > 0
    # Un servidor que calla tiene que fallar por el socket antes que por el límite blando.
    assert settings.EMAIL_TIMEOUT < send_confirmation_email.soft_time_limit
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
