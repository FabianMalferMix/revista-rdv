import pytest
from django.urls import reverse

from tests.factories import make_article
from tests.factories import publish as _publish

pytestmark = pytest.mark.django_db


def test_article_detail_ok_for_published(client):
    article = _publish(make_article(slug="visible", title="Reseña Visible"))
    resp = client.get(reverse("content:article_detail", args=[article.slug]))
    assert resp.status_code == 200
    assert b"Rese\xc3\xb1a Visible" in resp.content


def test_section_pagination(client):
    from apps.content.models import Section

    section = Section.objects.create(slug="sec", name="Sec")
    for i in range(15):
        _publish(make_article(slug=f"art{i}", section=section))
    url = reverse("content:section_detail", args=["sec"])
    page1 = client.get(url).context["articles"]
    assert page1.paginator.count == 15
    assert len(page1.object_list) == 12
    page2 = client.get(url + "?page=2").context["articles"]
    assert len(page2.object_list) == 3


def test_collection_index_and_detail(client):
    from apps.content.models import Collection, CollectionArticle, PublishStatus

    article = _publish(make_article(slug="en-coleccion", title="Pieza en Colección"))
    collection = Collection.objects.create(
        slug="antologia", title="Antología Demo", status=PublishStatus.PUBLISHED
    )
    CollectionArticle.objects.create(collection=collection, article=article, position=0)

    index = client.get(reverse("content:collection_index"))
    assert index.status_code == 200
    assert b"Antolog\xc3\xada Demo" in index.content

    detail = client.get(reverse("content:collection_detail", args=[collection.slug]))
    assert detail.status_code == 200
    assert b"Pieza en Colecci\xc3\xb3n" in detail.content
