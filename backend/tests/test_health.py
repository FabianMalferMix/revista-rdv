"""Sondas de salud: liveness (/healthz/) y readiness (/readyz/) — Lote F2-4."""

import secrets
import shutil
import time
from datetime import timedelta

import pytest
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from config import health

pytestmark = pytest.mark.django_db


def test_healthz_is_cheap_liveness(client):
    resp = client.get(reverse("healthz"))
    assert resp.status_code == 200
    assert resp.content == b"ok"


def test_loopback_always_allowed_for_internal_healthcheck():
    # La sonda del contenedor pega con Host=127.0.0.1; el loopback debe estar
    # permitido siempre para no dar DisallowedHost→400 en prod (Onda A).
    from django.conf import settings

    assert "127.0.0.1" in settings.ALLOWED_HOSTS
    assert "localhost" in settings.ALLOWED_HOSTS


def _all_up(monkeypatch, **overrides):
    """Todas las comprobaciones en verde, salvo las que se pasen con su causa."""
    checks = {name: (lambda: None) for name in health.CHECKS}
    for name, reason in overrides.items():
        checks[name] = lambda reason=reason: reason
    monkeypatch.setattr(health, "CHECKS", checks)


def test_readyz_ready_when_all_up(client, monkeypatch):
    _all_up(monkeypatch)
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


@pytest.mark.parametrize("name", sorted(health.CHECKS))
def test_readyz_503_names_what_fails_and_logs_why(client, monkeypatch, caplog, name):
    _all_up(monkeypatch, **{name: f"falla {name} por una causa"})
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 503
    assert resp.json()["checks"] == {n: n != name for n in health.CHECKS}
    assert f"readyz: falla {name} por una causa" in caplog.text


def test_an_unexpected_failure_in_a_check_is_an_error(client, monkeypatch, caplog):
    def broken():
        raise TypeError("comprobación rota")

    _all_up(monkeypatch)
    monkeypatch.setitem(health.CHECKS, "disk", broken)
    assert client.get(reverse("readyz")).status_code == 503
    (record,) = [r for r in caplog.records if r.name == "config.health"]
    assert record.levelname == "ERROR" and record.exc_info


def test_db_check_hits_real_database(db):
    assert health.check_database() is None


@pytest.fixture
def heartbeat_key(monkeypatch):
    """Una clave propia: el worker de desarrollo escribe la real en el mismo Redis."""
    key = f"resenas:latido:prueba:{secrets.token_hex(4)}"
    monkeypatch.setattr(health, "HEARTBEAT_KEY", key)
    yield key
    health._broker().delete(key)


@pytest.mark.integration
def test_stopped_tasks_turn_readyz_red_within_six_minutes(client, heartbeat_key, caplog):
    """Con beat detenido, el último latido envejece: a los cinco minutos, 503 y la causa."""
    health._broker().set(heartbeat_key, int(time.time()) - 301)
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 503
    assert resp.json()["checks"]["heartbeat"] is False
    assert "el último latido de las tareas es de hace 5 min" in caplog.text
    # Control positivo: en cuanto la tarea corre, el latido vuelve a estar al día.
    health.record_heartbeat()
    assert health.check_heartbeat() is None


@pytest.mark.integration
def test_publishing_scheduled_items_records_the_heartbeat(heartbeat_key):
    from apps.content.tasks import publish_due_items

    assert "no han dejado latido" in health.check_heartbeat()
    publish_due_items()
    assert health.check_heartbeat() is None


def test_overdue_scheduled_pieces_are_reported(make_article):
    assert health.check_scheduled() is None
    make_article(
        status=EditorialStatus.SCHEDULED, published_at=timezone.now() - timedelta(minutes=6)
    )
    assert health.check_scheduled() == "1 pieza(s) programada(s) vencida(s) sin publicar"


def test_pending_migrations_are_reported(db, monkeypatch):
    assert health.check_migrations() is None
    monkeypatch.setattr(MigrationExecutor, "migration_plan", lambda self, targets: [("x", False)])
    assert health.check_migrations() == "1 migración(es) sin aplicar"


def test_a_nearly_full_disk_is_reported(monkeypatch):
    assert health.check_disk() is None
    full = shutil._ntuple_diskusage(total=100, used=97, free=3)
    monkeypatch.setattr(health.shutil, "disk_usage", lambda root: full)
    assert "queda menos del 5 % libre" in health.check_disk()


@pytest.mark.integration
def test_readyz_real_infra_returns_ready(client, heartbeat_key):
    # En dev/CI la BD y el broker (Redis) están arriba: con el latido al día, readiness 200.
    health.record_heartbeat()
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 200, resp.json()
    assert resp.json()["status"] == "ready"


def test_a_cache_that_does_not_answer_turns_readyz_red(client, monkeypatch, settings):
    real = dict(health.CHECKS)
    _all_up(monkeypatch)
    # La comprobación de la caché, la de verdad, si /readyz/ la tiene en su lista.
    if "cache" in real:
        monkeypatch.setitem(health.CHECKS, "cache", real["cache"])
    assert client.get(reverse("readyz")).status_code == 200  # LocMem: nada que consultar
    settings.CACHES = {
        "default": {
            "BACKEND": "config.cache.ResilientRedisCache",
            "LOCATION": "redis://127.0.0.1:6399/0",
        }
    }
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 503
    assert resp.json()["checks"]["cache"] is False
