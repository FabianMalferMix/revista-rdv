import pytest

from tests.factories import make_article

pytestmark = pytest.mark.django_db


def test_reading_time_is_derived():
    article = make_article(body="palabra " * 400)
    assert article.reading_time == 2  # 400 palabras / 200


def test_reading_time_minimum_one():
    article = make_article(body="una sola línea corta")
    assert article.reading_time >= 1
