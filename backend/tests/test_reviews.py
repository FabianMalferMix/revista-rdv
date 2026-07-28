"""Integridad de la bibliografía (reviews.Work) — Onda A (post-auditoría)."""

import pytest
from django.db import IntegrityError, transaction

from apps.reviews.models import Work

pytestmark = pytest.mark.django_db


def test_multiple_works_without_isbn_allowed():
    # "" se coacciona a NULL en save(): varias obras sin ISBN conviven (antes el 2.º
    # "" chocaba con el UNIQUE plano y daba IntegrityError/500 en el admin).
    a = Work.objects.create(slug="obra-1", title="Poemario 1", isbn="")
    Work.objects.create(slug="obra-2", title="Poemario 2")  # isbn omitido
    a.refresh_from_db()
    assert a.isbn is None


def test_duplicate_real_isbn_rejected():
    Work.objects.create(slug="obra-a", title="A", isbn="978-956-000-1")
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.create(slug="obra-b", title="B", isbn="978-956-000-1")
