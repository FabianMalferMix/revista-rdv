"""La purga cuenta desde el último cambio de estado, no desde la llegada.

Quien vuelve a suscribirse no pierde su alta nueva, y un envío rechazado hoy no se borra la
semana siguiente por haber llegado hace meses, porque la política de privacidad promete contar
desde la resolución. Esa fecha sigue al estado del envío: se fija al resolverlo y se borra si
vuelve a revisión.
"""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.community import services
from apps.community.models import NewsletterSubscriber
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db


def _purge():
    call_command("purge_stale_data", days=180, verbosity=0)


def _ago(days):
    return timezone.now() - timedelta(days=days)


def test_resubscribing_restarts_the_purge_clock():
    """Re-suscripción cruzada con la purga: el alta vieja no arrastra a la nueva."""
    back = NewsletterSubscriber.objects.create(email="vuelve@example.com")
    gone = NewsletterSubscriber.objects.create(email="se-fue@example.com")
    for sub in (back, gone):
        sub.unsubscribe()
    NewsletterSubscriber.objects.update(created_at=_ago(200), status_changed_at=_ago(190))
    services.subscribe("vuelve@example.com")
    _purge()
    assert NewsletterSubscriber.objects.filter(email="vuelve@example.com").exists()
    # Control positivo: quien no volvió se purga, como siempre.
    assert not NewsletterSubscriber.objects.filter(email="se-fue@example.com").exists()


def test_a_late_rejection_waits_its_full_term():
    """Resolución tardía: llegó hace 200 días y se rechazó hoy; se guarda 180 desde hoy."""
    late = Submission.objects.create(
        author_name="A", author_email="a@example.com", type="otro", title="Tarde", body="x"
    )
    old = Submission.objects.create(
        author_name="B", author_email="b@example.com", type="otro", title="Vieja", body="x"
    )
    for submission in (late, old):
        submission.status = Submission.Status.REJECTED
        submission.save()
    Submission.objects.update(created_at=_ago(200))
    Submission.objects.filter(pk=old.pk).update(resolved_at=_ago(181))
    _purge()
    assert Submission.objects.filter(pk=late.pk).exists()
    assert not Submission.objects.filter(pk=old.pk).exists()


def test_the_resolution_date_follows_the_status():
    submission = Submission.objects.create(
        author_name="A", author_email="a@example.com", type="otro", title="T", body="x"
    )
    assert submission.resolved_at is None
    submission.status = Submission.Status.WITHDRAWN
    submission.save()
    assert submission.resolved_at is not None
    submission.status = Submission.Status.IN_REVIEW
    submission.save()
    assert submission.resolved_at is None
