"""Integridad de la bibliografía (reviews.Work) y sus vistas públicas."""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.content.models import EditorialStatus
from apps.reviews.models import BookAuthor, Work

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


# ── Vistas públicas de reviews (hallazgo #10: sin prueba) ───────────────────


def test_work_detail_renders_and_lists_published_review_only(client, make_article):
    work = Work.objects.create(slug="poemario-x", title="Poemario X")
    pub = make_article(
        status=EditorialStatus.PUBLISHED, slug="resena-pub", title="Reseña Publicada"
    )
    pub.reviewed_works.add(work)
    draft = make_article(status=EditorialStatus.DRAFT, slug="resena-draft", title="Reseña Borrador")
    draft.reviewed_works.add(work)
    resp = client.get(reverse("reviews:work_detail", args=[work.slug]))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Poemario X" in content
    assert "Reseña Publicada" in content  # la reseña publicada aparece
    assert "Reseña Borrador" not in content  # el borrador no


def test_work_detail_404_for_unknown_slug(client):
    assert client.get(reverse("reviews:work_detail", args=["no-existe"])).status_code == 404


def test_bookauthor_detail_renders_with_its_works(client):
    author = BookAuthor.objects.create(slug="autora-x", name="Autora X")
    work = Work.objects.create(slug="obra-de-autora", title="Obra De Autora")
    work.authors.add(author)
    resp = client.get(reverse("reviews:bookauthor_detail", args=[author.slug]))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Autora X" in content
    assert "Obra De Autora" in content


def test_bookauthor_detail_404_for_unknown_slug(client):
    assert client.get(reverse("reviews:bookauthor_detail", args=["no-existe"])).status_code == 404
