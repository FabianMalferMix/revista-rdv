import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import ArticleStatus, ReviewedWork
from apps.reviews.models import Publisher, Work
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db


def _publish(article):
    article.status = ArticleStatus.PUBLISHED
    article.published_at = timezone.now()
    article.save()
    return article


def test_home_shows_published_hides_drafts(client, make_article):
    _publish(make_article(slug="pub", title="Artículo Publicado"))
    make_article(slug="draft", title="Artículo Borrador", status=ArticleStatus.DRAFT)
    resp = client.get(reverse("content:home"))
    assert resp.status_code == 200
    assert b"Art\xc3\xadculo Publicado" in resp.content
    assert b"Art\xc3\xadculo Borrador" not in resp.content


def test_article_detail_404_for_draft(client, make_article):
    draft = make_article(slug="oculto", status=ArticleStatus.DRAFT)
    resp = client.get(reverse("content:article_detail", args=[draft.slug]))
    assert resp.status_code == 404


def test_article_detail_ok_for_published(client, make_article):
    article = _publish(make_article(slug="visible", title="Reseña Visible"))
    resp = client.get(reverse("content:article_detail", args=[article.slug]))
    assert resp.status_code == 200
    assert b"Rese\xc3\xb1a Visible" in resp.content


def test_submission_post_creates(client):
    resp = client.post(
        reverse("submissions:submit"),
        data={
            "author_name": "Ana",
            "author_email": "ana@example.com",
            "type": "reseña",
            "title": "Mi propuesta",
            "body": "cuerpo",
            "apodo": "",
        },
    )
    assert resp.status_code == 302
    assert Submission.objects.filter(title="Mi propuesta").exists()


def test_submission_honeypot_is_dropped(client):
    resp = client.post(
        reverse("submissions:submit"),
        data={
            "author_name": "Bot",
            "author_email": "bot@spam.com",
            "type": "otro",
            "title": "spam",
            "body": "x",
            "apodo": "bot",
        },
    )
    assert resp.status_code == 302
    assert not Submission.objects.filter(title="spam").exists()


def test_publisher_page_aggregates_reviews(client, make_article):
    publisher = Publisher.objects.create(slug="editorial-x", name="Editorial X")
    work = Work.objects.create(slug="obra-x", title="Obra X", publisher=publisher)
    article = _publish(make_article(slug="resena-x", title="Reseña Agregada"))
    ReviewedWork.objects.create(article=article, work=work, is_primary=True)
    resp = client.get(reverse("reviews:publisher_detail", args=[publisher.slug]))
    assert resp.status_code == 200
    assert b"Rese\xc3\xb1a Agregada" in resp.content


def test_section_pagination(client, make_article):
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


def test_submission_file_only_for_editors(client, editor, autor):
    from django.core.files.uploadedfile import SimpleUploadedFile

    submission = Submission.objects.create(
        author_name="A",
        author_email="a@a.com",
        type="reseña",
        title="Privado",
        body="cuerpo",
        file=SimpleUploadedFile("m.txt", b"contenido-secreto"),
    )
    url = reverse("submissions:file", args=[submission.pk])

    assert client.get(url).status_code == 302  # anónimo → login

    client.force_login(autor)  # staff pero no editor
    assert client.get(url).status_code == 404

    client.force_login(editor)
    resp = client.get(url)
    assert resp.status_code == 200
    assert b"contenido-secreto" in b"".join(resp.streaming_content)
