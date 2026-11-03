"""Lo que falla de verdad se ve como un error: llega a Sentry, y el log dice qué.

Lo esperado y manejado (un servicio caído, que la página ya resuelve) va como WARNING de una
línea; lo inesperado, como ERROR con su traza, que es lo que Sentry convierte en un evento.
Antes casi todo era WARNING con traza: invisible para Sentry y ruidoso en el log, y el
buscador convertía un error de programación en «sin resultados».
"""

import pytest
from django.core.files.storage import FileSystemStorage
from django.db import OperationalError, ProgrammingError
from django.urls import reverse

from config import cache as resilient
from tests.factories import make_image

pytestmark = pytest.mark.django_db


def _search(client, monkeypatch, error):
    def broken(*args, **kwargs):
        raise error

    monkeypatch.setattr("apps.content.views.coincidencias_por_nombre", broken)
    client.raise_request_exception = False
    return client.get(reverse("content:search"), {"q": "umbral"})


def test_a_programming_error_in_search_reaches_sentry_as_an_error(
    sentry_events, client, monkeypatch
):
    response = _search(client, monkeypatch, ProgrammingError('column "titulo" does not exist'))
    assert response.status_code == 500
    events = sentry_events()
    assert events and {event["level"] for event in events} == {"error"}
    assert "ProgrammingError" in {e["exception"]["values"][-1]["type"] for e in events}


def test_a_dropped_connection_in_search_shows_no_results_and_is_an_error(
    sentry_events, client, monkeypatch
):
    response = _search(client, monkeypatch, OperationalError("server closed the connection"))
    assert response.status_code == 200
    (event,) = sentry_events()
    assert event["level"] == "error"
    assert event["exception"]["values"][-1]["type"] == "OperationalError"


def test_the_cache_reports_one_error_per_interval(monkeypatch, caplog):
    monkeypatch.setattr(resilient, "_last_error", None)
    store = resilient.ResilientRedisCache("redis://127.0.0.1:1/0", {})
    assert store.get("clave", "por defecto") == "por defecto"
    assert store.get("clave") is None
    records = [r for r in caplog.records if r.name == "config.cache"]
    assert [(r.levelname, bool(r.exc_info)) for r in records] == [
        ("ERROR", True),
        ("WARNING", False),
    ]


def test_a_file_that_cannot_be_deleted_is_an_error_naming_its_row(monkeypatch, caplog):
    asset = make_image("huerfana")
    pk, name = asset.pk, asset.file.name

    def refuse(self, name):
        raise OSError("disco de solo lectura")

    monkeypatch.setattr(FileSystemStorage, "delete", refuse)
    asset.delete()
    records = [r for r in caplog.records if r.name == "apps.media.filecleanup"]
    assert records and all(r.levelname == "ERROR" and r.exc_info for r in records)
    assert f"No se pudo borrar el archivo {name!r} de media.MediaAsset pk={pk}" in [
        r.getMessage() for r in records
    ]
