"""El HTML de autor se depura al mostrarlo, no solo al guardarlo.

Un cuerpo escrito sin pasar por `save()` (con `update()`, loaddata o una migración de datos) no
mete en la ficha ni scripts ni atributos de htmx: el filtro `authored_html` lo depura al pintarlo,
y su contenedor lleva `hx-disable`. Ninguna plantilla usa `|safe`: ese filtro es el único camino.
"""

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from apps.content.models import Article, Page
from tests.factories import publish

BACKEND_DIR = Path(__file__).resolve().parent.parent
HOSTILE = (
    "<p>Texto legítimo.</p><script>alert(1)</script>"
    '<div hx-post="/admin/auth/user/add/" hx-trigger="load">cebo</div>'
    '<a href="javascript:alert(1)" onclick="alert(1)">enlace</a>'
)


def _body(response):
    body = BeautifulSoup(response.content, "html.parser").select_one("div.body")
    assert body.has_attr("hx-disable")
    return body


def _assert_clean(body):
    assert "Texto legítimo." in body.get_text()
    assert body.select_one("script") is None
    assert not [
        tag for tag in body.find_all(True) if any(a.startswith(("hx-", "on")) for a in tag.attrs)
    ]
    assert all(not a["href"].startswith("javascript:") for a in body.select("a[href]"))


@pytest.mark.django_db
def test_a_text_body_written_without_save_is_cleaned_on_the_page(client):
    article = publish(Article.objects.create(slug="cuerpo", title="Cuerpo", body="<p>x</p>"))
    Article.objects.filter(pk=article.pk).update(body=HOSTILE)
    _assert_clean(_body(client.get(reverse("content:article_detail", args=["cuerpo"]))))


@pytest.mark.django_db
def test_a_page_body_written_without_save_is_cleaned_on_the_page(client):
    page = Page.objects.create(slug="aviso", title="Aviso", body="<p>x</p>", status="published")
    Page.objects.filter(pk=page.pk).update(body=HOSTILE)
    _assert_clean(_body(client.get(reverse("content:page_detail", args=["aviso"]))))


def test_no_template_marks_text_as_safe_by_hand():
    templates = [
        *BACKEND_DIR.glob("templates/**/*.html"),
        *BACKEND_DIR.glob("apps/*/templates/**/*.html"),
    ]
    assert len(templates) > 50
    unsafe = re.compile(r"\|\s*safe(seq)?\b|\{%\s*autoescape\s+off")
    offenders = [
        str(p.relative_to(BACKEND_DIR)) for p in templates if unsafe.search(p.read_text("utf-8"))
    ]
    assert offenders == []
