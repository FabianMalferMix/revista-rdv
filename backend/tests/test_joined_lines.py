"""Las líneas de datos unidos con « · » no dejan ningún separador colgando.

Las arma la etiqueta `{% joined %}` (apps/site/templatetags/joined.py): un dato que falta se omite
con su separador. Antes, cada plantilla ponía sus separadores a mano, y la ficha de una
publicación sin año abría su línea con « · », y la de una editorial sin país, con « · Sitio web».
"""

import pytest
from django.template import engines

from apps.reviews.models import Publisher
from tests.factories import make_publication, soup

pytestmark = pytest.mark.django_db


def _render(source, **context):
    return engines["django"].from_string("{% load joined %}" + source).render(context)


def _text(element):
    return " ".join(element.get_text(" ", strip=True).split())


def test_a_publication_without_year_does_not_open_its_line_with_a_separator(client):
    editorial = Publisher.objects.create(slug="ediciones-sur", name="Ediciones Sur")
    sin_anio = make_publication(year=None, publisher=editorial, isbn="978-956-00-0000-0")
    meta = soup(client, sin_anio.get_absolute_url()).select_one(".ficha-texto .meta")
    assert _text(meta) == "Ediciones Sur · ISBN 978-956-00-0000-0"
    # Control: con año, el año abre la línea y lo demás sigue igual.
    con_anio = make_publication(year=2024, publisher=editorial)
    meta = soup(client, con_anio.get_absolute_url()).select_one(".ficha-texto .meta")
    assert _text(meta) == "2024 · Ediciones Sur"
    assert meta.a["href"] == editorial.get_absolute_url()


def test_a_publisher_without_country_shows_its_website_without_a_separator(client):
    editorial = Publisher.objects.create(
        slug="sin-pais", name="Sin País", website="https://sinpais.example"
    )
    make_publication(publisher=editorial)  # su ficha existe porque la respalda una publicación
    meta = soup(client, editorial.get_absolute_url()).select_one(".index-head .meta")
    assert _text(meta) == "Sitio web"
    assert meta.a["href"] == "https://sinpais.example"
    # Control: con país, el país va primero.
    editorial.country = "Chile"
    editorial.save()
    meta = soup(client, editorial.get_absolute_url()).select_one(".index-head .meta")
    assert _text(meta) == "Chile · Sitio web"


def test_joined_skips_the_empty_parts_wherever_they_are():
    plantilla = "{% joined %}{{ a }}{% part %}{{ b }}{% part %}{{ c }}{% endjoined %}"
    assert _render(plantilla, a="", b="Dos", c="Tres") == "Dos · Tres"
    assert _render(plantilla, a="Uno", b="", c="Tres") == "Uno · Tres"
    assert _render(plantilla, a="Uno", b="Dos", c="   ") == "Uno · Dos"
    assert _render(plantilla, a="", b="", c="") == ""
    # El espacio que rodea una parte en la plantilla no se pinta.
    con_blancos = "{% joined %}\n  {{ a }}\n{% part %}\n  {{ b }}\n{% endjoined %}"
    assert _render(con_blancos, a=1, b=2) == "1 · 2"
    # Otro separador, como el del título de la pestaña.
    titulo = '{% joined " — " %}{{ a }}{% part %}{{ b }}{% endjoined %}'
    assert _render(titulo, a="", b="Sitio") == "Sitio"
    assert _render(titulo, a="Poemas", b="Sitio") == "Poemas — Sitio"


def test_joined_keeps_the_markup_of_the_template_and_escapes_the_data():
    salida = _render(
        '{% joined %}<a href="/obra/">{{ a }}</a>{% part %}{{ b }}{% endjoined %}',
        a="Uno & otro",
        b="<script>alert(1)</script>",
    )
    assert salida == '<a href="/obra/">Uno &amp; otro</a> · &lt;script&gt;alert(1)&lt;/script&gt;'
