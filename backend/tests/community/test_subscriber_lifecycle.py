"""El ciclo de vida del suscriptor.

Una dirección es una sola fila, aunque llegue con otra caja o con espacios, y la confirmación
no se reenvía antes de diez minutos. La baja anula el enlace de confirmación pendiente, y quien
vuelve después tiene que confirmar otra vez.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.community import services
from apps.community.models import NewsletterSubscriber

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def test_two_signups_with_different_case_leave_one_row(client):
    for email in ("Ana@Correo.cl", "  ana@correo.CL "):
        response = client.post(reverse("community:subscribe"), {"email": email, "apodo": ""})
        assert response.status_code == 302
    assert list(NewsletterSubscriber.objects.values_list("email", flat=True)) == ["ana@correo.cl"]


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
