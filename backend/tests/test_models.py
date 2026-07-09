import pytest
from django.contrib.postgres.search import SearchQuery
from django.db import IntegrityError

from apps.community.models import Comment
from apps.content.models import Article, ArticleStatus
from apps.people.models import Contributor, SocialLink

pytestmark = pytest.mark.django_db


def test_reading_time_is_derived(make_article):
    article = make_article(body="palabra " * 400)
    assert article.reading_time == 2  # 400 palabras / 200


def test_reading_time_minimum_one(make_article):
    article = make_article(body="una sola línea corta")
    assert article.reading_time >= 1


def test_search_vector_populated(make_article):
    article = make_article(title="Reseña de poesía chilena", status=ArticleStatus.PUBLISHED)
    match = Article.objects.filter(search_vector=SearchQuery("poesía", config="spanish"))
    assert article in match


def test_comment_requires_user_xor_guest(make_article):
    article = make_article()
    # Ni usuario ni invitado → viola el CHECK XOR.
    with pytest.raises(IntegrityError):
        Comment.objects.create(article=article, body="texto")


def test_comment_guest_is_valid(make_article):
    article = make_article()
    comment = Comment.objects.create(
        article=article, guest_name="Ana", guest_email="ana@example.com", body="hola"
    )
    assert comment.pk is not None


def test_body_is_sanitized_on_save(make_article):
    article = make_article(
        body='<p>Texto legítimo</p><script>alert("xss")</script>'
    )
    assert "<script" not in article.body
    assert "alert" not in article.body  # el contenido del script también se elimina
    assert "<p>Texto legítimo</p>" in article.body


def test_sanitizer_keeps_allowed_formatting(make_article):
    article = make_article(
        body='<p><strong>Negrita</strong> y <a href="https://x.cl">enlace</a>.</p>'
    )
    assert "<strong>Negrita</strong>" in article.body
    assert 'href="https://x.cl"' in article.body


def test_sociallink_unique_per_platform():
    contributor = Contributor.objects.create(slug="c1", display_name="Colaboradora")
    SocialLink.objects.create(contributor=contributor, platform="twitter", url="https://x/a")
    with pytest.raises(IntegrityError):
        SocialLink.objects.create(
            contributor=contributor, platform="twitter", url="https://x/b"
        )
