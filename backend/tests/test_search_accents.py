"""La búsqueda pliega los acentos con una sola regla, y el título pesa más que el cuerpo.

Los textos y los poemas se indexan y se buscan con la misma configuración de la base, que quita
los acentos también de las letras sin descomposición Unicode (ł, ø): «Wisława», «Søren» y
«canción» se encuentran escritos con y sin diacríticos, como los nombres de las personas. En los
poemas cuenta también el epígrafe, donde va la dedicatoria. El vector es una columna generada: un
`update()` lo rehace. Un tipo de resultado desconocido es un
error, no una actividad.
"""

import pytest
from django.urls import reverse

from apps.content import services
from apps.content.models import Article, Poem
from apps.people.models import Contributor
from tests.factories import publish

pytestmark = pytest.mark.django_db
WORDS = [("Wisława", "Wislawa"), ("Søren", "Soren"), ("canción", "cancion")]


def _search(client, q):
    return client.get(reverse("content:search"), {"q": q}).content.decode()


@pytest.mark.parametrize(("written", "plain"), WORDS)
def test_a_word_is_found_with_and_without_its_diacritics(client, written, plain):
    article = publish(
        Article.objects.create(
            slug="texto", title="Un texto", body=f"<p>Leímos a {written} en voz alta.</p>"
        )
    )
    poem = publish(Poem.objects.create(slug="poema", title="Un poema", body=f"La voz de {written}"))
    person = Contributor.objects.create(
        slug="persona", display_name=f"{written} Lira", is_member=True
    )
    for q in (written, plain):
        page = _search(client, q)
        for url in (article.get_absolute_url(), poem.get_absolute_url(), person.get_absolute_url()):
            assert f'href="{url}"' in page, (q, url)


def test_a_text_with_the_word_in_its_title_comes_first(client):
    body_only = publish(
        Article.objects.create(
            slug="cuerpo", title="Notas de lectura", body="<p>Una canción vieja.</p>"
        )
    )
    in_title = publish(
        Article.objects.create(slug="titulo", title="La canción", body="<p>Otra cosa.</p>")
    )
    page = _search(client, "cancion")
    first, second = in_title.get_absolute_url(), body_only.get_absolute_url()
    assert f'href="{second}"' in page
    assert page.index(f'href="{first}"') < page.index(f'href="{second}"')


@pytest.mark.parametrize("q", ["Wisława", "Wislawa"])
def test_a_poem_is_found_by_the_name_in_its_epigraph(client, q):
    """La dedicatoria va en el epígrafe: el nombre no está ni en el título ni en los versos."""
    dedicated = publish(
        Poem.objects.create(
            slug="dedicado", title="Puerto", epigraph="Para Wisława", body="El agua vuelve."
        )
    )
    other = publish(Poem.objects.create(slug="otro", title="Otro", body="El agua vuelve."))
    page = _search(client, q)
    assert f'href="{dedicated.get_absolute_url()}"' in page
    assert f'href="{other.get_absolute_url()}"' not in page
    assert f'href="{other.get_absolute_url()}"' in _search(client, "agua")


def test_a_poem_with_the_word_in_its_title_comes_before_its_epigraph(client):
    dedicated = publish(
        Poem.objects.create(
            slug="dedicado", title="Puerto", epigraph="Para Wisława", body="El agua vuelve."
        )
    )
    in_title = publish(Poem.objects.create(slug="titulo", title="Wisława", body="Otra cosa."))
    page = _search(client, "Wislawa")
    first, second = in_title.get_absolute_url(), dedicated.get_absolute_url()
    assert f'href="{second}"' in page
    assert page.index(f'href="{first}"') < page.index(f'href="{second}"')


def test_the_index_follows_a_body_written_without_save(client):
    article = publish(Article.objects.create(slug="texto", title="Un texto", body="<p>Nada.</p>"))
    Article.objects.filter(pk=article.pk).update(body="<p>Una elegía para Miłosz.</p>")
    assert f'href="{article.get_absolute_url()}"' in _search(client, "Milosz")


def test_an_unknown_result_type_is_an_error_not_an_event(client, monkeypatch):
    row = {"tipo": "obra", "slug": "x", "titulo": "Obra", "dato": "", "lugar": "", "fecha": None}
    monkeypatch.setattr(
        "apps.content.views.coincidencias_por_nombre",
        lambda term, top: [{**row, "anio": None, "integrante": False}],
    )
    with pytest.raises(ValueError, match="obra"):
        _search(client, "obra")
    assert [kind for kind, _ in services.SEARCH_TYPES] == [
        "persona",
        "poema",
        "texto",
        "registro",
        "publicacion",
        "actividad",
    ]
