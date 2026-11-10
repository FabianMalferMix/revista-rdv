"""«Participan» se lee igual en las tres fichas que lo llevan: la publicación, la actividad y el
registro. Lo pinta una sola parcial, `partials/_participan.html`: el rótulo de los datos de la
ficha y los nombres, cada uno hacia su página si la tiene. Eran tres bloques copiados, y el del
registro iba con otro título.

Tiene página quien la tiene en su ficha (`Contributor.objects.visible()`): las integrantes y
quien firma algo publicado. Quien solo participa no la tiene, y su enlace llevaría a un 404: se
la nombra sin enlace, y el pie de la publicación no le abre una puerta. Se sabe con la misma
consulta de la lista, sin una más por persona.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.content.models import PoemContributor
from apps.people.models import Contributor
from tests.factories import (
    make_event,
    make_poem,
    make_publication,
    make_published_poem,
    make_recording,
    soup,
)

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


@pytest.fixture
def people():
    """Una integrante y quien firma un poema publicado sin ser integrante, que tienen página, y
    una invitada que participa sin ser integrante ni firmar nada publicado (su borrador no
    cuenta), que no la tiene."""
    ana = Contributor.objects.create(slug="ana", display_name="Ana Pizarro", is_member=True)
    luis = Contributor.objects.create(slug="luis", display_name="Luis Mora")
    PoemContributor.objects.create(poem=make_published_poem(), contributor=luis)
    berta = Contributor.objects.create(slug="berta", display_name="Berta Invitada")
    PoemContributor.objects.create(poem=make_poem(), contributor=berta)
    return ana, luis, berta


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


@pytest.mark.parametrize("make", [make_publication, make_event, make_recording])
def test_a_participant_without_a_page_is_named_without_a_link(client, make, people):
    ana, luis, berta = people
    # La página de la invitada responde 404; las de las otras dos, 200.
    assert client.get(berta.get_absolute_url()).status_code == 404
    assert [client.get(c.get_absolute_url()).status_code for c in (ana, luis)] == [200, 200]
    ficha = make()
    ficha.participants.add(ana, luis, berta)
    assert _participants(soup(client, ficha.get_absolute_url())) == (
        ["rotulo", "ficha-rotulo"],
        [("Ana Pizarro", ana.get_absolute_url()), ("Luis Mora", luis.get_absolute_url())],
        "Ana Pizarro · Berta Invitada · Luis Mora",
    )


def test_the_publication_footer_opens_a_door_only_to_who_has_a_page(client, people):
    ana, luis, berta = people
    publicacion = make_publication()
    publicacion.participants.add(ana, luis, berta)
    sopa = soup(client, publicacion.get_absolute_url())
    puertas = [
        (li.select_one(".rotulo").get_text(), li.a.get_text(), li.a["href"])
        for li in sopa.select("nav.pie-entidad li")
    ]
    assert [(texto, url) for rotulo, texto, url in puertas if rotulo == "Más de"] == [
        ("Ana Pizarro", ana.get_absolute_url()),
        ("Luis Mora", luis.get_absolute_url()),
    ]
    # Control: la invitada participa, y la ficha la nombra.
    assert "Berta Invitada" in _participants(sopa)[2]


@pytest.mark.parametrize("make", [make_publication, make_event, make_recording])
def test_knowing_who_has_a_page_costs_no_query_per_person(client, make, people):
    """La ficha hace las mismas consultas con una persona que con tres: quién tiene página llega
    con la lista de quienes participan."""
    ana, luis, berta = people
    ficha = make()
    ficha.participants.add(ana)
    url = ficha.get_absolute_url()
    soup(client, url)  # en caliente: el perfil del sitio ya existe
    with CaptureQueriesContext(connection) as una:
        soup(client, url)
    ficha.participants.add(luis, berta)
    with CaptureQueriesContext(connection) as tres:
        sopa = soup(client, url)
    # Control: la ficha nombra a las tres.
    assert _participants(sopa)[2] == "Ana Pizarro · Berta Invitada · Luis Mora"
    assert len(tres) == len(una), "una consulta más por persona"
