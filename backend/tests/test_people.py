import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import ArticleContributor, ArticleStatus
from apps.media.models import Recording
from apps.people.models import Contributor

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


def test_member_detail_shows_profile_and_published_articles(client, member, make_article):
    art = make_article(
        slug="texto-pub",
        title="Texto Publicado",
        status=ArticleStatus.PUBLISHED,
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


def test_member_detail_shows_only_published_recordings(client, member):
    pub = Recording.objects.create(
        slug="lectura-uno", title="Lectura Uno", embed_url="https://example.com/v/1", published=True
    )
    pub.participants.add(member)
    unpub = Recording.objects.create(
        slug="lectura-dos", title="Lectura Dos", embed_url="https://example.com/v/2"
    )
    unpub.participants.add(member)

    resp = client.get(reverse("people:member_detail", args=[member.slug]))
    assert b"Lectura Uno" in resp.content
    assert b"Lectura Dos" not in resp.content


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


def test_contributor_detail_redirects_members_to_profile(client, member):
    resp = client.get(reverse("content:contributor_detail", args=[member.slug]))
    assert resp.status_code == 302
    assert resp.url == reverse("people:member_detail", args=[member.slug])


def test_get_absolute_url_depends_on_membership(member):
    externa = Contributor.objects.create(slug="externa", display_name="Externa")
    assert member.get_absolute_url() == reverse("people:member_detail", args=[member.slug])
    assert externa.get_absolute_url() == reverse("content:contributor_detail", args=["externa"])


def test_home_shows_member_grid(client, member):
    resp = client.get(reverse("content:home"))
    assert resp.status_code == 200
    assert b"Poeta Uno" in resp.content
