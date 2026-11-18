"""Las fichas de las integrantes: el índice enseña a las activas; la ficha de cada una, también
la de una histórica, con su poética y lo que tiene publicado, y no existe para quien no es
integrante. Cada persona tiene una sola dirección (`url_for_person`), la misma en la firma de un
texto, en la búsqueda y en la otra ruta, que redirige."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import ArticleContributor, EditorialStatus
from apps.people.models import Contributor, url_for_person
from tests.factories import make_article

pytestmark = pytest.mark.django_db


@pytest.fixture
def member(db):
    return Contributor.objects.create(
        slug="poeta-uno",
        display_name="Poeta Uno",
        is_member=True,
        role="Fundador",
        member_since=2019,
        short_bio="Poeta y gestor.",
        poetics="El poema como respiración.",
    )


def test_member_index_lists_only_active_members(client, member):
    Contributor.objects.create(slug="externa", display_name="Colaboradora Externa")
    Contributor.objects.create(
        slug="historico", display_name="Integrante Histórico", is_member=True, active=False
    )
    resp = client.get(reverse("people:member_index"))
    assert resp.status_code == 200
    assert b"Poeta Uno" in resp.content
    assert b"Colaboradora Externa" not in resp.content
    assert b"Integrante Hist\xc3\xb3rico" not in resp.content


def test_member_detail_shows_profile_and_published_articles(client, member):
    art = make_article(
        slug="texto-pub",
        title="Texto Publicado",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    ArticleContributor.objects.create(article=art, contributor=member)
    draft = make_article(slug="texto-borrador", title="Texto Borrador")
    ArticleContributor.objects.create(article=draft, contributor=member)

    resp = client.get(reverse("people:member_detail", args=[member.slug]))
    assert resp.status_code == 200
    assert b"El poema como respiraci\xc3\xb3n." in resp.content
    assert b"Texto Publicado" in resp.content
    assert b"Texto Borrador" not in resp.content


def test_member_detail_404_for_non_member(client):
    Contributor.objects.create(slug="externa", display_name="Externa")
    resp = client.get(reverse("people:member_detail", args=["externa"]))
    assert resp.status_code == 404


def test_historical_member_profile_stays_accessible(client):
    Contributor.objects.create(
        slug="fundadora-historica",
        display_name="Fundadora Histórica",
        is_member=True,
        active=False,
    )
    resp = client.get(reverse("people:member_detail", args=["fundadora-historica"]))
    assert resp.status_code == 200
    assert b"hist\xc3\xb3rico" in resp.content


@pytest.mark.parametrize(
    ("is_member", "address", "other_address"),
    [
        (True, "/integrante/una-voz/", "/colaborador/una-voz/"),
        (False, "/colaborador/una-voz/", "/integrante/una-voz/"),
    ],
    ids=["member", "collaborator"],
)
def test_a_person_has_one_address_wherever_she_is_linked(client, is_member, address, other_address):
    """La regla vive en `url_for_person`: lleva a la misma ficha la firma de un texto, el
    resultado de la búsqueda y la otra ruta, que redirige."""
    person = Contributor.objects.create(slug="una-voz", display_name="Una Voz", is_member=is_member)
    article = make_article(status=EditorialStatus.PUBLISHED)
    article.authors.add(person)

    assert url_for_person("una-voz", is_member) == address
    byline = client.get(article.get_absolute_url()).content.decode()
    assert f'href="{address}">Una Voz</a>' in byline
    found = client.get(reverse("site:search"), {"q": "Una Voz"}).content.decode()
    assert f'href="{address}">Una Voz</a>' in found
    redirected = client.get(other_address)
    assert (redirected.status_code, redirected["Location"]) == (302, address)
    assert client.get(address).status_code == 200
