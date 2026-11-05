"""Los comandos de mantenimiento terminan su trabajo y avisan de lo que no pudieron hacer.

La purga de datos personales no se detiene porque un adjunto o un grupo fallen: purga lo demás y
sale con error, nombrando lo que quedó; si la base no responde, la tarea lo reintenta. El comando
de imágenes procesa todas aunque una falle de manera inesperada, y dice cuál.
"""

import logging
from datetime import timedelta
from io import BytesIO

import pytest
from axes.models import AccessAttempt
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.db.models.query import QuerySet
from django.utils import timezone
from PIL import Image

from apps.community.models import NewsletterSubscriber
from apps.media.management.commands import generate_image_derivatives
from apps.media.models import MediaAsset
from apps.submissions.management.commands.purge_stale_data import AXES_RETENTION_DAYS
from apps.submissions.models import Submission
from apps.submissions.tasks import purge_stale_pii


def _stale():
    """Lo que la purga tiene que borrar: un envío rechazado con su manuscrito, una suscripción
    nunca confirmada y un intento de acceso, todos caducados."""
    long_ago = timezone.now() - timedelta(days=200)
    sub = Submission.objects.create(
        author_name="A",
        author_email="a@x.cl",
        type="poesía",
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


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_an_image_that_fails_unexpectedly_does_not_stop_the_others(monkeypatch, caplog):
    assets = []
    for name in ("una", "dos"):
        buf = BytesIO()
        Image.new("RGB", (600, 400), (10, 20, 30)).save(buf, format="JPEG")
        assets.append(
            MediaAsset.objects.create(
                file=SimpleUploadedFile(f"{name}.jpg", buf.getvalue()), alt_text=name
            )
        )
    broken, fine = assets
    original = generate_image_derivatives.process_image

    def failing(pk):
        if pk == broken.pk:
            raise ValueError("algo inesperado")
        return original(pk)

    monkeypatch.setattr(generate_image_derivatives, "process_image", failing)
    with pytest.raises(CommandError, match=rf"recursos {broken.pk}\)"):
        call_command("generate_image_derivatives", verbosity=0)
    assert MediaAsset.objects.get(pk=fine.pk).border_color
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR] == [
        f"No se pudo procesar la imagen del recurso {broken.pk}"
    ]
