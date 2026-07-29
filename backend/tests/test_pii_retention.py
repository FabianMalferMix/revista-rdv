"""Retención de PII y redacción de secretos en los registros (S-18, S-20).

S-18: la purga prometía en la política borrar los datos de quien se da de baja, pero
solo cubría suscriptores nunca confirmados y envíos resueltos; los dados de baja y los
intentos de acceso de django-axes (IP + usuario tecleado) se acumulaban sin caducidad.

S-20: los enlaces del boletín llevan el token en la RUTA, así que acababan en el log
JSON y —lo más serio— en el nombre de la transacción enviada a Sentry, es decir a un
tercero. Quien leyera esos registros podía dar de baja suscripciones ajenas.
"""

import logging
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from config.redaction import RedactTokensFilter, redact_path, sentry_before_send

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
VIEJO = timezone.now() - timedelta(days=400)


def _suscriptor(email, status):
    sub = NewsletterSubscriber.objects.create(email=email, status=status, token="t-" + email)
    NewsletterSubscriber.objects.filter(pk=sub.pk).update(created_at=VIEJO)
    return sub


# ── S-18: la purga cubre lo que la política promete ───────


def test_la_purga_borra_a_quien_se_dio_de_baja():
    """Pedir la baja es pedir que dejemos de tratar los datos: conservarlos para siempre
    contradice lo que dice la política de privacidad."""
    _suscriptor("baja@example.com", S.UNSUBSCRIBED)
    call_command("purge_stale_data", days=180, verbosity=0)
    assert not NewsletterSubscriber.objects.filter(email="baja@example.com").exists()


def test_la_purga_sigue_borrando_a_los_nunca_confirmados():
    _suscriptor("pendiente@example.com", S.PENDING)
    call_command("purge_stale_data", days=180, verbosity=0)
    assert not NewsletterSubscriber.objects.filter(email="pendiente@example.com").exists()


def test_la_purga_respeta_a_los_suscriptores_confirmados():
    """Un confirmado antiguo NO se borra: consintió y no ha revocado."""
    _suscriptor("confirmado@example.com", S.CONFIRMED)
    call_command("purge_stale_data", days=180, verbosity=0)
    assert NewsletterSubscriber.objects.filter(email="confirmado@example.com").exists()


def test_la_purga_respeta_lo_reciente():
    NewsletterSubscriber.objects.create(email="reciente@example.com", status=S.UNSUBSCRIBED)
    call_command("purge_stale_data", days=180, verbosity=0)
    assert NewsletterSubscriber.objects.filter(email="reciente@example.com").exists()


def test_la_purga_borra_los_intentos_de_acceso_caducados():
    """django-axes guarda IP y usuario tecleado: son datos personales y no tenían
    ninguna política de retención."""
    from axes.models import AccessAttempt

    from apps.submissions.management.commands.purge_stale_data import AXES_RETENTION_DAYS

    viejo = AccessAttempt.objects.create(
        username="alguien", ip_address="203.0.113.5", failures_since_start=1
    )
    AccessAttempt.objects.filter(pk=viejo.pk).update(
        attempt_time=timezone.now() - timedelta(days=AXES_RETENTION_DAYS + 1)
    )
    reciente = AccessAttempt.objects.create(
        username="otro", ip_address="203.0.113.6", failures_since_start=1
    )

    call_command("purge_stale_data", verbosity=0)

    assert not AccessAttempt.objects.filter(pk=viejo.pk).exists()
    assert AccessAttempt.objects.filter(pk=reciente.pk).exists()


def test_dry_run_no_borra_nada():
    _suscriptor("baja2@example.com", S.UNSUBSCRIBED)
    call_command("purge_stale_data", days=180, dry_run=True, verbosity=0)
    assert NewsletterSubscriber.objects.filter(email="baja2@example.com").exists()


# ── S-20: los tokens no salen en los registros ────────────


def test_se_redacta_el_token_de_las_rutas_del_boletin():
    assert redact_path("/novedades/baja/SECRETO-123/") == "/novedades/baja/<redactado>/"
    assert redact_path("/novedades/confirmar/SECRETO-123/") == "/novedades/confirmar/<redactado>/"
    assert redact_path("https://sitio.cl/novedades/baja/abc/") == (
        "https://sitio.cl/novedades/baja/<redactado>/"
    )


def test_no_se_toca_lo_que_no_lleva_secreto():
    for ruta in ["/textos/", "/buscar/?q=umbral", "/novedades/", "/admin/"]:
        assert redact_path(ruta) == ruta


def test_el_filtro_de_logging_redacta_el_mensaje():
    registro = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Not Found: %s",
        args=("/novedades/baja/SECRETO-123/",),
        exc_info=None,
    )
    assert RedactTokensFilter().filter(registro) is True
    assert "SECRETO-123" not in registro.getMessage()
    assert "<redactado>" in registro.getMessage()


def test_sentry_no_recibe_el_token():
    """Es el punto más serio: sin esto el token viajaba a un TERCERO."""
    evento = {
        "transaction": "/novedades/baja/SECRETO-123/",
        "request": {"url": "https://sitio.cl/novedades/baja/SECRETO-123/"},
    }
    limpio = sentry_before_send(evento, {})
    assert "SECRETO-123" not in limpio["transaction"]
    assert "SECRETO-123" not in limpio["request"]["url"]


def test_la_redaccion_nunca_rompe_el_reporte():
    """Un `before_send` que lanza excepción haría perder el evento de error."""
    assert sentry_before_send({"transaction": None, "request": "no-es-dict"}, {}) is not None
    assert sentry_before_send({}, {}) == {}
