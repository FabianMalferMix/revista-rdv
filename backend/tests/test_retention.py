"""Retención/purga de PII (comando purge_stale_data) — Onda D."""

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
    type(obj).objects.filter(pk=obj.pk).update(created_at=timezone.now() - timedelta(days=days))


def _submission(**kw):
    defaults = {
        "author_name": "A",
        "author_email": "a@x.cl",
        "type": "reseña",
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


def test_purge_dry_run_deletes_nothing():
    old = NewsletterSubscriber.objects.create(email="dry@x.cl", status=NS.PENDING)
    _age(old, 300)
    call_command("purge_stale_data", days=180, dry_run=True)
    assert NewsletterSubscriber.objects.filter(pk=old.pk).exists()
