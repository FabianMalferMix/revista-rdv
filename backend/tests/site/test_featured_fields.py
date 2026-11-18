"""El panel solo ofrece los destacados que cambian algo en el sitio.

Los registros y las publicaciones tienen su casilla, porque la tirada y el estante de la
portada la leen. Los textos, los poemas, las actividades y las menciones de prensa no la
tienen, y el panel tampoco ofrece la obra principal de una reseña ni el idioma de una obra:
nada los leería.
"""

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def panel(client, editor):
    client.force_login(editor)
    return client


def _campos(panel, vista):
    respuesta = panel.get(reverse(vista))
    assert respuesta.status_code == 200
    formulario = BeautifulSoup(respuesta.content, "html.parser").select_one("#content-main form")
    return {campo["name"] for campo in formulario.select("[name]")}


@pytest.mark.parametrize(
    "vista,campo",
    [
        ("admin:content_article_add", "featured"),
        ("admin:content_poem_add", "featured"),
        ("admin:agenda_event_add", "featured"),
        ("admin:showcase_pressmention_add", "featured"),
        ("admin:reviews_work_add", "language"),
    ],
)
def test_panel_offers_no_field_without_effect(panel, vista, campo):
    campos = _campos(panel, vista)
    assert "title" in campos or "outlet" in campos
    assert campo not in campos


def test_review_form_does_not_mark_a_primary_work(panel):
    campos = _campos(panel, "admin:content_article_add")
    assert any(c.endswith("-work") for c in campos)
    assert not any(c.endswith("-is_primary") for c in campos)


@pytest.mark.parametrize("vista", ["admin:media_recording_add", "admin:showcase_publication_add"])
def test_panel_keeps_the_featured_boxes_the_home_page_reads(panel, vista):
    assert "featured" in _campos(panel, vista)
