"""«Participan» se lee igual en las tres fichas que lo llevan: la publicación, la actividad y el
registro. Lo pinta una sola parcial, `partials/_participan.html`: el rótulo de los datos de la
ficha y los nombres, cada uno hacia su página. Eran tres bloques copiados, y el del registro iba
con otro título."""

import pytest

from apps.people.models import Contributor
from tests.factories import make_event, make_publication, make_recording, soup

pytestmark = pytest.mark.django_db


def _participants(sopa):
    """El rótulo «Participan» de la página y los enlaces que lo siguen, o None si no lo hay."""
    rotulo = next((h2 for h2 in sopa.select("h2") if h2.get_text() == "Participan"), None)
    if rotulo is None:
        return None
    nombres = rotulo.find_next_sibling("p")
    return (
        rotulo["class"],
        [(a.get_text(), a["href"]) for a in nombres.select("a")],
        " ".join(nombres.get_text(" ", strip=True).split()),
    )


@pytest.mark.parametrize("make", [make_publication, make_event, make_recording])
def test_the_three_pages_name_their_participants_the_same_way(client, make):
    ana = Contributor.objects.create(slug="ana", display_name="Ana Pizarro", is_member=True)
    luis = Contributor.objects.create(slug="luis", display_name="Luis Mora", is_member=True)
    con_gente, sin_gente = make(), make()
    con_gente.participants.add(ana, luis)
    assert _participants(soup(client, con_gente.get_absolute_url())) == (
        ["rotulo", "ficha-rotulo"],
        [("Ana Pizarro", ana.get_absolute_url()), ("Luis Mora", luis.get_absolute_url())],
        "Ana Pizarro · Luis Mora",
    )
    sopa = soup(client, sin_gente.get_absolute_url())
    assert sopa.h1.get_text(strip=True) == sin_gente.title  # control: es su ficha
    assert _participants(sopa) is None, "sin participantes, no se pinta el rótulo"
