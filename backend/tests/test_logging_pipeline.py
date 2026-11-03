"""El token del boletín no sale en claro de ningún proceso que escriba logs.

La redacción sigue a las rutas del URLconf: renombrar la de confirmación, o añadir otra
ruta con token, no deja el token en claro sin tocar nada más. Y llega a todos los
procesos: a los extras anidados que adjunta Celery, al worker y a beat (que antes perdían
el formato y el filtro) y a gunicorn.
"""

import json
import logging
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from django.urls import reverse

from config import redaction
from config.celery import app as celery_app
from config.logformat import JsonFormatter
from config.redaction import RedactTokensFilter, redact_path

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Valor anodino, para que gitleaks no lo tome por una credencial.
VALUE = "no-es-una-credencial"


def test_a_renamed_token_route_is_still_redacted(settings):
    settings.ROOT_URLCONF = "tests.urls_renamed_token_routes"
    for name in ("community:confirm", "community:one_click_unsubscribe"):
        path = reverse(name, args=[VALUE])
        assert not path.startswith("/novedades/")
        assert redact_path(f"GET {path} 404") == f"GET {path.replace(VALUE, '<redactado>')} 404"


def test_redaction_fails_closed_if_the_routes_cannot_be_read(monkeypatch, settings):
    settings.ROOT_URLCONF = "tests.urls_renamed_token_routes"

    def broken():
        raise RuntimeError("URLconf roto")

    monkeypatch.setattr(redaction, "token_route_prefixes", broken)
    monkeypatch.setattr(redaction, "_patterns", {})
    assert redact_path("GET /boletin/salir/abc/") == redaction.SIN_PATRON


def test_nested_extras_from_celery_are_redacted():
    """Celery adjunta los argumentos de la tarea como un diccionario con listas dentro."""
    url = reverse("community:unsubscribe", args=[VALUE])
    record = logging.LogRecord(
        "celery.worker.strategy", logging.INFO, __file__, 1, "Task received", (), None
    )
    record.data = {"args": (f"https://revista.example.org{url}",), "kwargs": {"urls": [url]}}
    line = JsonFormatter().format(record)
    assert VALUE not in line
    assert json.loads(line)["data"]["kwargs"]["urls"] == ["/novedades/baja/<redactado>/"]


@pytest.fixture
def restore_root_logging():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_a_worker_line_comes_out_as_redacted_json(settings, capsys, restore_root_logging):
    """Como en producción: Celery configura el log del worker y una tarea registra un extra
    con una URL con token."""
    production = deepcopy(settings.LOGGING)
    production["handlers"]["console"]["formatter"] = "json"
    settings.LOGGING = production
    celery_app.log.already_setup = False
    celery_app.log.setup_logging_subsystem()

    root = logging.getLogger()
    assert any(isinstance(f, RedactTokensFilter) for h in root.handlers for f in h.filters)
    url = reverse("community:confirm", args=[VALUE])
    logging.getLogger("celery.app.trace").warning("Task failed", extra={"data": {"args": [url]}})
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert VALUE not in line
    assert json.loads(line)["data"]["args"] == ["/novedades/confirmar/<redactado>/"]


def test_gunicorn_logs_json_with_redaction():
    """gunicorn lee gunicorn.conf.py de su directorio de trabajo; un error al atender una
    petición sale en JSON y sin el token."""
    script = (
        "import django, logging.config, runpy; django.setup(); "
        "logging.config.dictConfig(runpy.run_path('gunicorn.conf.py')['logconfig_dict']); "
        f"logging.getLogger('gunicorn.error').error('Error handling request %s', '/novedades/baja/{VALUE}/')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-500:]
    line = json.loads(result.stderr.strip().splitlines()[-1])
    assert line["logger"] == "gunicorn.error"
    assert line["message"] == "Error handling request /novedades/baja/<redactado>/"
