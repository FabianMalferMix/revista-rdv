"""El panel respeta el consentimiento del boletín y el estado de los envíos.

El doble opt-in es la única prueba del consentimiento, y el panel dejaba saltárselo: marcar
a alguien como confirmado a mano, con una fecha inventada. En los envíos, se podía reescribir
lo que mandó la autora y cambiar el estado sin fecha, del que depende la purga.
"""

import pytest
from django.contrib.admin.models import LogEntry
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
SUBSCRIBERS = "/admin/community/newslettersubscriber/"
SUBMISSIONS = "/admin/submissions/submission/"


@pytest.fixture
def panel(client, editor):
    client.force_login(editor)
    return client


def _pending():
    return NewsletterSubscriber.objects.create(
        email="ana@example.com",
        token="baja-de-ana",
        confirm_token="alta-de-ana",
        confirm_token_at=timezone.now(),
    )


def test_the_panel_cannot_mark_a_subscriber_as_confirmed(panel):
    sub = _pending()
    page = panel.get(f"{SUBSCRIBERS}{sub.pk}/change/").content.decode()
    assert 'name="status"' not in page
    assert "baja-de-ana" not in page and "alta-de-ana" not in page  # los tokens no se ven
    assert panel.post(f"{SUBSCRIBERS}{sub.pk}/change/", {"status": "confirmed"}).status_code == 302
    sub.refresh_from_db()
    assert sub.status == S.PENDING and sub.confirmed_at is None


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_adding_a_subscriber_by_hand_sends_the_confirmation(
    panel, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = panel.post(f"{SUBSCRIBERS}add/", {"email": " Nuevo@Example.com "})
    assert response.status_code == 302
    sub = NewsletterSubscriber.objects.get()
    assert (sub.email, sub.status) == ("nuevo@example.com", S.PENDING)
    assert [message.to for message in mail.outbox] == [["nuevo@example.com"]]


def test_unsubscribing_from_the_panel_leaves_a_record(panel):
    sub = _pending()
    sub.confirm()
    response = panel.post(SUBSCRIBERS, {"action": "do_unsubscribe", "_selected_action": [sub.pk]})
    assert response.status_code == 302
    sub.refresh_from_db()
    assert sub.status == S.UNSUBSCRIBED
    assert LogEntry.objects.get(object_id=str(sub.pk)).get_change_message() == (
        "Dado de baja (antes: Confirmado)."
    )


def _submission():
    return Submission.objects.create(
        author_name="Ana",
        author_email="ana@example.com",
        type="poesía",
        title="Umbral",
        body="Versos",
    )


def test_the_panel_does_not_rewrite_what_the_author_sent(panel):
    submission = _submission()
    page = panel.get(f"{SUBMISSIONS}{submission.pk}/change/").content.decode()
    for field in ("author_name", "author_email", "title", "body", "status"):
        assert f'name="{field}"' not in page
    assert 'name="notes"' in page  # control positivo: las notas del equipo sí se editan
    panel.post(
        f"{SUBMISSIONS}{submission.pk}/change/", {"author_email": "otra@example.com", "notes": "x"}
    )
    submission.refresh_from_db()
    assert submission.author_email == "ana@example.com" and submission.notes == "x"


def test_rejecting_from_the_panel_dates_it_and_records_the_previous_state(panel, editor):
    submission = _submission()
    response = panel.post(
        SUBMISSIONS, {"action": "move_to_rejected", "_selected_action": [submission.pk]}
    )
    assert response.status_code == 302
    submission.refresh_from_db()
    assert submission.status == Submission.Status.REJECTED
    assert submission.resolved_at is not None
    assert submission.reviewer == editor
    assert LogEntry.objects.get(object_id=str(submission.pk)).get_change_message() == (
        "Estado: Recibido → Rechazado."
    )
