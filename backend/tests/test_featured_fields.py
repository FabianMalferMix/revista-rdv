"""El panel solo ofrece los destacados que cambian algo en el sitio.

Los registros y las publicaciones conservan su casilla: la tirada y el estante de la
portada la leen. La de textos, poemas, actividades y menciones de prensa, la obra principal
de una reseña y el idioma de una obra no los leía nadie, y salieron. La tirada lleva como
mucho TIRADA_SIZE registros, y el panel no deja destacar uno más.
"""

import pytest
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.media.models import TIRADA_SIZE
from tests.factories import make_recording

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
def test_panel_no_longer_offers_fields_without_effect(panel, vista, campo):
    campos = _campos(panel, vista)
    assert "title" in campos or "outlet" in campos
    assert campo not in campos


def test_review_form_no_longer_marks_a_primary_work(panel):
    campos = _campos(panel, "admin:content_article_add")
    assert any(c.endswith("-work") for c in campos)
    assert not any(c.endswith("-is_primary") for c in campos)


@pytest.mark.parametrize("vista", ["admin:media_recording_add", "admin:showcase_publication_add"])
def test_panel_keeps_the_featured_boxes_the_home_page_reads(panel, vista):
    assert "featured" in _campos(panel, vista)


def test_one_recording_more_than_the_tirada_holds_is_refused():
    for _ in range(TIRADA_SIZE - 1):
        make_recording(featured=True)
    ultimo_que_cabe = make_recording(featured=True)
    ultimo_que_cabe.full_clean()  # ya destacado: se puede seguir editando
    sobra = make_recording()
    sobra.featured = True
    with pytest.raises(ValidationError, match="quita uno"):
        sobra.full_clean()
    ultimo_que_cabe.featured = False
    ultimo_que_cabe.save()
    sobra.full_clean()
