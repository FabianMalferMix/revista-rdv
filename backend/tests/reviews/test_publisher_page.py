"""La página de una editorial reúne las reseñas publicadas de sus obras."""

import pytest
from django.urls import reverse

from apps.content.models import ReviewedWork
from apps.reviews.models import Publisher, Work
from tests.factories import make_article
from tests.factories import publish as _publish

pytestmark = pytest.mark.django_db


def test_publisher_page_aggregates_reviews(client):
    publisher = Publisher.objects.create(slug="editorial-x", name="Editorial X")
    work = Work.objects.create(slug="obra-x", title="Obra X", publisher=publisher)
    article = _publish(make_article(slug="resena-x", title="Reseña Agregada"))
    ReviewedWork.objects.create(article=article, work=work)
    resp = client.get(reverse("reviews:publisher_detail", args=[publisher.slug]))
    assert resp.status_code == 200
    assert b"Rese\xc3\xb1a Agregada" in resp.content
