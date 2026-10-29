"""Las fichas de obra, editorial, autora de obra y colaboradora existen solo si algo publicado
las respalda; lo demás responde 404 y no va al sitemap. Una integrante tiene ficha siempre.

Cada prueba recorre el mismo camino: sin respaldo, nada; con un respaldo que no está publicado,
tampoco; al publicarse, la ficha y el sitemap.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import ArticleContributor, EditorialStatus, PoemContributor, ReviewedWork
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from tests.factories import make_publication

pytestmark = pytest.mark.django_db
S = EditorialStatus


def _publish(piece):
    piece.status = S.PUBLISHED
    piece.published_at = timezone.now()
    piece.save()


def _public(client, url):
    """(la ficha responde 200, la dirección está en el sitemap)."""
    in_sitemap = url in client.get(reverse("sitemap")).content.decode()
    return client.get(url).status_code == 200, in_sitemap


@pytest.fixture
def catalogue():
    publisher = Publisher.objects.create(slug="editorial-x", name="Editorial X")
    author = BookAuthor.objects.create(slug="autora-x", name="Autora X")
    work = Work.objects.create(slug="obra-x", title="Obra X", publisher=publisher)
    work.authors.add(author)
    return work, publisher, author


def _urls(work, publisher, author):
    return [
        reverse("reviews:work_detail", args=[work.slug]),
        reverse("reviews:publisher_detail", args=[publisher.slug]),
        reverse("reviews:bookauthor_detail", args=[author.slug]),
    ]


def test_the_catalogue_appears_when_its_review_is_published(client, catalogue, make_article):
    work, publisher, author = catalogue
    urls = _urls(work, publisher, author)
    assert [_public(client, url) for url in urls] == [(False, False)] * 3
    review = make_article(title="La reseña de la obra", status=S.IN_REVIEW)
    ReviewedWork.objects.create(article=review, work=work)
    assert [_public(client, url) for url in urls] == [(False, False)] * 3
    _publish(review)
    assert [_public(client, url) for url in urls] == [(True, True)] * 3
    assert "La reseña de la obra" in client.get(urls[0]).content.decode()


def test_a_work_that_is_a_published_publication_has_its_page(client, catalogue):
    work, publisher, author = catalogue
    work.publicacion = make_publication(slug="libro-propio", title="Libro propio", published=False)
    work.save()
    urls = _urls(work, publisher, author)
    assert [_public(client, url) for url in urls] == [(False, False)] * 3
    work.publicacion.published = True
    work.publicacion.save()
    assert [_public(client, url) for url in urls] == [(True, True)] * 3


def test_a_publisher_page_shows_the_collective_publications(client):
    publisher = Publisher.objects.create(slug="editorial-y", name="Editorial Y")
    url = reverse("reviews:publisher_detail", args=[publisher.slug])
    hidden = make_publication(slug="oculta", title="Plaquette oculta", publisher=publisher)
    hidden.published = False
    hidden.save()
    assert _public(client, url) == (False, False)
    make_publication(slug="visible", title="Plaquette visible", publisher=publisher)
    assert _public(client, url) == (True, True)
    content = client.get(url).content.decode()
    assert "Plaquette visible" in content
    assert "Plaquette oculta" not in content
    # Sin obras reseñadas, la ficha no anuncia un catálogo vacío.
    assert "Catálogo reseñado" not in content


@pytest.mark.parametrize("model", ["article", "poem"])
def test_a_signature_has_a_page_only_with_something_published(
    client, make_article, make_poem, model
):
    guest = Contributor.objects.create(slug="firma-x", display_name="Firma Equis")
    url = reverse("content:contributor_detail", args=[guest.slug])
    search = reverse("content:search") + "?q=equis"
    make = make_article if model == "article" else make_poem
    piece = make(title="La pieza firmada", status=S.DRAFT)
    link = ArticleContributor if model == "article" else PoemContributor
    link.objects.create(**{model: piece, "contributor": guest})
    assert client.get(url).status_code == 404
    assert url not in client.get(search).content.decode()
    _publish(piece)
    response = client.get(url)
    assert response.status_code == 200
    assert "La pieza firmada" in response.content.decode()
    assert url in client.get(search).content.decode()


def test_a_member_always_has_a_page(client):
    member = Contributor.objects.create(
        slug="integrante-x", display_name="Integrante", is_member=True
    )
    response = client.get(reverse("content:contributor_detail", args=[member.slug]))
    assert response.status_code == 302
    assert client.get(response.url).status_code == 200
