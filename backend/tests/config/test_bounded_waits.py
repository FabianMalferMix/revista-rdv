"""Nada espera sin plazo, y el worker no crece con las CPU del servidor.

Con gthread, el --timeout de gunicorn no corta una petición colgada: sin un plazo, una
consulta lenta retendría un hilo mientras durara. La base cancela la consulta que pasa del
plazo, y una conexión que se cortó se comprueba antes de reutilizarla.
"""

import os
import subprocess
import sys
from unittest import mock

from django.conf import settings

from config.celery import app

BACKEND_DIR = settings.BASE_DIR
SLEEP = "import django; django.setup(); from django.db import connection; connection.cursor().execute('SELECT pg_sleep(1)'); print('terminó')"


def _sleep_one_second(**env):
    return subprocess.run(
        [sys.executable, "-c", SLEEP],
        cwd=BACKEND_DIR,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings", **env},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_a_query_over_the_statement_timeout_fails():
    result = _sleep_one_second(DB_STATEMENT_TIMEOUT_MS="200")
    assert result.returncode != 0
    assert "canceling statement due to statement timeout" in result.stderr


def test_the_release_can_lift_the_statement_timeout_to_migrate():
    """Control positivo: con el PGOPTIONS del release, la misma consulta termina."""
    result = _sleep_one_second(DB_STATEMENT_TIMEOUT_MS="200", PGOPTIONS="-c statement_timeout=0")
    assert result.returncode == 0, result.stderr[-300:]
    assert "terminó" in result.stdout


def test_the_worker_starts_two_processes_on_an_eight_core_server():
    with mock.patch("celery.worker.worker.cpu_count", return_value=8):
        worker = app.WorkController(hostname="prueba@local", pool_cls="prefork")
    assert worker.concurrency == 2
    assert worker.max_tasks_per_child == 200


def test_every_task_declares_its_time_limits():
    """Cada tarea de las apps declara sus dos límites, con su porqué junto a ella: los globales de
    settings son para las tareas de Celery mismo, no un valor que se hereda sin decidirlo."""
    app.loader.import_default_modules()
    own = {name: task for name, task in app.tasks.items() if name.startswith("apps.")}
    # Control: se leen las tareas de las apps, también la que ya los declaraba.
    assert "apps.media.tasks.process_image" in own and len(own) >= 4, sorted(own)
    undeclared = [
        name
        for name, task in own.items()
        if task.soft_time_limit is None or task.time_limit is None
    ]
    assert sorted(undeclared) == []
    for name, task in own.items():
        assert 0 < task.soft_time_limit < task.time_limit, name
