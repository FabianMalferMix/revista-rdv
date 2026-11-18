"""La purga de datos personales caducados (comando purge_stale_data): lo viejo se borra; lo
confirmado, lo aceptado y lo reciente se conservan. Entran también los intentos de acceso que
guarda django-axes, con la IP y el usuario tecleado: por su cuenta, axes solo borra los caducados
cuando alguien vuelve a entrar, salir o fallar."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db
NS = NewsletterSubscriber.Status
SS = Submission.Status


def _age(obj, days):
    """Envejece la fila: su alta y, que es desde donde mide la purga, su último cambio de
    estado (suscriptores) o su resolución (envíos resueltos)."""
    moment = timezone.now() - timedelta(days=days)
    fields = {"created_at": moment}
    names = {field.name for field in type(obj)._meta.fields}
    if "status_changed_at" in names:
        fields["status_changed_at"] = moment
    if "resolved_at" in names and obj.resolved_at:
        fields["resolved_at"] = moment
    type(obj).objects.filter(pk=obj.pk).update(**fields)


def _submission(**kw):
    defaults = {
        "author_name": "A",
        "author_email": "a@x.cl",
        "type": "resena",
        "title": "t",
        "body": "b",
    }
    defaults.update(kw)
    return Submission.objects.create(**defaults)


def test_purge_removes_stale_and_keeps_active():
    old_pending = NewsletterSubscriber.objects.create(email="viejo@x.cl", status=NS.PENDING)
    _age(old_pending, 200)
    confirmed = NewsletterSubscriber.objects.create(email="ok@x.cl", status=NS.CONFIRMED)
    _age(confirmed, 200)  # confirmado: se conserva
    recent = NewsletterSubscriber.objects.create(email="nuevo@x.cl", status=NS.PENDING)  # reciente

    old_rejected = _submission(status=SS.REJECTED)
    _age(old_rejected, 200)
    accepted = _submission(author_email="b@x.cl", status=SS.ACCEPTED)
    _age(accepted, 200)  # aceptado: se conserva

    call_command("purge_stale_data", days=180)

    assert not NewsletterSubscriber.objects.filter(pk=old_pending.pk).exists()
    assert NewsletterSubscriber.objects.filter(pk=confirmed.pk).exists()
    assert NewsletterSubscriber.objects.filter(pk=recent.pk).exists()
    assert not Submission.objects.filter(pk=old_rejected.pk).exists()
    assert Submission.objects.filter(pk=accepted.pk).exists()


def test_la_purga_respeta_lo_reciente():
    NewsletterSubscriber.objects.create(email="reciente@example.com", status=NS.UNSUBSCRIBED)
    call_command("purge_stale_data", days=180, verbosity=0)
    assert NewsletterSubscriber.objects.filter(email="reciente@example.com").exists()


def test_la_purga_borra_los_intentos_de_acceso_caducados():
    """django-axes guarda IP y usuario tecleado, que son datos personales: la purga los borra
    pasados `AXES_RETENTION_DAYS`."""
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


def test_purge_dry_run_deletes_nothing():
    old = NewsletterSubscriber.objects.create(email="dry@x.cl", status=NS.PENDING)
    _age(old, 300)
    call_command("purge_stale_data", days=180, dry_run=True)
    assert NewsletterSubscriber.objects.filter(pk=old.pk).exists()


def test_purge_task_wraps_command():
    # La tarea Celery (programada en beat, semanal) ejecuta la purga.
    from apps.submissions.tasks import purge_stale_pii

    old = NewsletterSubscriber.objects.create(email="task@x.cl", status=NS.PENDING)
    _age(old, 300)
    purge_stale_pii()
    assert not NewsletterSubscriber.objects.filter(pk=old.pk).exists()
