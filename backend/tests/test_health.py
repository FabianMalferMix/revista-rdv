"""Sondas de salud: liveness (/healthz/) y readiness (/readyz/) — Lote F2-4."""

import pytest
from django.urls import reverse

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


def test_readyz_ready_when_all_up(client, monkeypatch):
    monkeypatch.setattr("apps.content.views._db_ok", lambda: True)
    monkeypatch.setattr("apps.content.views._broker_ok", lambda: True)
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["checks"] == {"database": True, "broker": True}


def test_readyz_503_when_broker_down(client, monkeypatch):
    monkeypatch.setattr("apps.content.views._db_ok", lambda: True)
    monkeypatch.setattr("apps.content.views._broker_ok", lambda: False)
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "not-ready"
    assert data["checks"]["broker"] is False


def test_readyz_503_when_db_down(client, monkeypatch):
    monkeypatch.setattr("apps.content.views._db_ok", lambda: False)
    monkeypatch.setattr("apps.content.views._broker_ok", lambda: True)
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 503
    assert resp.json()["checks"]["database"] is False


def test_db_check_hits_real_database(client):
    # La sonda de BD funciona contra la base real de test.
    from apps.content.views import _db_ok

    assert _db_ok() is True


@pytest.mark.integration
def test_readyz_real_infra_returns_ready(client):
    # En dev/CI la BD y el broker (Redis) están arriba: readiness real 200.
    # Requiere Redis vivo (broker); marcado como integration (no hermetico).
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
