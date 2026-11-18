"""La purga de datos personales caducados (comando purge_stale_data): lo viejo se borra; lo
confirmado, lo aceptado y lo reciente se conservan. Entran también los intentos de acceso que
guarda django-axes, con la IP y el usuario tecleado: por su cuenta, axes solo borra los caducados
cuando alguien vuelve a entrar, salir o fallar.

Un envío se va con su manuscrito. Si un adjunto o un grupo fallan, la purga borra lo demás, nombra
lo que quedó (en el mensaje o con un ERROR en el log) y sale con error; si lo que falla es la base,
que no responde, sale con ese mismo error, y la tarea la reintenta."""

import logging
from datetime import timedelta

import pytest
from axes.models import AccessAttempt
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.db.models.query import QuerySet
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.submissions.management.commands.purge_stale_data import AXES_RETENTION_DAYS
from apps.submissions.models import Submission
from apps.submissions.tasks import purge_stale_pii

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
    old = NewsletterSubscriber.objects.create(email="task@x.cl", status=NS.PENDING)
    _age(old, 300)
    purge_stale_pii()
    assert not NewsletterSubscriber.objects.filter(pk=old.pk).exists()


def _stale():
    """Lo que la purga tiene que borrar: un envío rechazado con su manuscrito, una suscripción
    nunca confirmada y un intento de acceso, todos caducados."""
    long_ago = timezone.now() - timedelta(days=200)
    sub = Submission.objects.create(
        author_name="A",
        author_email="a@x.cl",
        type="poesia",
        title="t",
        body="b",
        status=Submission.Status.REJECTED,
        file=SimpleUploadedFile("manuscrito.pdf", b"%PDF-1.4 contenido"),
    )
    Submission.objects.filter(pk=sub.pk).update(resolved_at=long_ago)
    pending = NewsletterSubscriber.objects.create(email="viejo@x.cl")
    NewsletterSubscriber.objects.filter(pk=pending.pk).update(status_changed_at=long_ago)
    attempt = AccessAttempt.objects.create(
        username="alguien", ip_address="203.0.113.5", failures_since_start=1
    )
    AccessAttempt.objects.filter(pk=attempt.pk).update(
        attempt_time=timezone.now() - timedelta(days=AXES_RETENTION_DAYS + 1)
    )
    return sub, pending, attempt


def _gone(*rows):
    return not any(type(row).objects.filter(pk=row.pk).exists() for row in rows)


@pytest.mark.django_db(transaction=True)
def test_the_purge_deletes_the_manuscript_with_its_submission():
    sub, pending, attempt = _stale()
    storage, name = sub.file.storage, sub.file.name
    assert storage.exists(name)  # control: el manuscrito estaba guardado
    call_command("purge_stale_data", days=180, verbosity=0)
    assert _gone(sub, pending, attempt)
    assert not storage.exists(name)


@pytest.mark.django_db(transaction=True)
def test_a_manuscript_that_cannot_be_deleted_does_not_stop_the_purge(monkeypatch):
    sub, pending, attempt = _stale()
    storage, name = sub.file.storage, sub.file.name

    def refuse(name):
        raise PermissionError("sin permiso para borrar")

    monkeypatch.setattr(storage, "delete", refuse)
    with pytest.raises(CommandError, match=rf"1 adjuntos \(envíos {sub.pk}\)"):
        call_command("purge_stale_data", days=180, verbosity=0)
    assert _gone(sub, pending, attempt)
    assert storage.exists(name)


@pytest.mark.parametrize("error", [RuntimeError, OperationalError])
def test_a_group_that_fails_does_not_stop_the_others(monkeypatch, caplog, error):
    sub, pending, attempt = _stale()
    original = QuerySet.delete

    def failing(self):
        if self.model is NewsletterSubscriber:
            raise error("tabla bloqueada")
        return original(self)

    monkeypatch.setattr(QuerySet, "delete", failing)
    expected = OperationalError if error is OperationalError else CommandError
    with pytest.raises(expected):
        call_command("purge_stale_data", days=180, verbosity=0)
    assert _gone(sub, attempt)
    assert NewsletterSubscriber.objects.filter(pk=pending.pk).exists()
    failures = [r for r in caplog.records if r.levelno == logging.ERROR and r.exc_info]
    assert [r.getMessage() for r in failures] == [
        "La purga de suscriptores pendientes falló",
        "La purga de suscriptores dados de baja falló",
    ]


def test_the_purge_task_retries_when_the_database_does_not_answer():
    assert OperationalError in purge_stale_pii.autoretry_for
    assert purge_stale_pii.retry_kwargs["max_retries"] == 3
