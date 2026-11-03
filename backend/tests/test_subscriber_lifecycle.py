"""El ciclo de vida del suscriptor y de los envíos, y la purga que mide desde él.

La purga borraba por la fecha de llegada: quien volvía a suscribirse podía perder su alta
nueva, y un envío rechazado hoy se borraba la semana siguiente si había llegado hace meses,
aunque la política de privacidad promete contar desde la resolución.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.community import services
from apps.community.models import NewsletterSubscriber
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def _purge():
    call_command("purge_stale_data", days=180, verbosity=0)


def _ago(days):
    return timezone.now() - timedelta(days=days)


def test_two_signups_with_different_case_leave_one_row(client):
    for email in ("Ana@Correo.cl", "  ana@correo.CL "):
        client.post(reverse("community:subscribe"), {"email": email, "apodo": ""})
    assert list(NewsletterSubscriber.objects.values_list("email", flat=True)) == ["ana@correo.cl"]


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
        author_name="A", author_email="a@example.com", title="Tarde", body="x"
    )
    old = Submission.objects.create(
        author_name="B", author_email="b@example.com", title="Vieja", body="x"
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
        author_name="A", author_email="a@example.com", title="T", body="x"
    )
    assert submission.resolved_at is None
    submission.status = Submission.Status.WITHDRAWN
    submission.save()
    assert submission.resolved_at is not None
    submission.status = Submission.Status.IN_REVIEW
    submission.save()
    assert submission.resolved_at is None


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_the_confirmation_is_not_resent_within_ten_minutes(
    client, django_capture_on_commit_callbacks
):
    def signup():
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                reverse("community:subscribe"), {"email": "z@example.com", "apodo": ""}
            )
        return response

    first, second = signup(), signup()
    assert len(mail.outbox) == 1
    assert first.status_code == second.status_code == 302  # la misma respuesta
    NewsletterSubscriber.objects.update(confirm_token_at=timezone.now() - timedelta(minutes=11))
    signup()
    assert len(mail.outbox) == 2


def test_unsubscribing_voids_a_pending_confirmation_link(client):
    sub = services.subscribe("anula@example.com")
    link = reverse("community:confirm", args=[sub.confirm_token])
    assert client.get(link).status_code == 200
    sub.unsubscribe()
    assert client.get(link).status_code == 404


def test_coming_back_after_unsubscribing_requires_confirming_again():
    sub = services.subscribe("regresa@example.com")
    sub.confirm()
    sub.unsubscribe()
    sub = services.subscribe("regresa@example.com")
    assert sub.status == S.PENDING
    assert sub.confirmed_at is None
