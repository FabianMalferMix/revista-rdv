"""La vista previa del equipo: la ficha de algo sin publicar se sirve a quien puede verlo en el panel.

Con la franja «Vista previa: no publicado», sin indexar y sin guardarse en cachés compartidas. Un
anónimo recibe 404, como siempre, y una autora no ve los borradores ajenos. Lo publicado se sirve
igual que antes, sin franja.

La vista previa enseña la pieza como la verá quien lee, pero lo que la rodea puede no tener página
pública todavía: quien firma sin nada publicado, la editorial sin nada publicado, la obra que
nadie ha reseñado. Se nombran sin enlace, porque el suyo llevaría a un 404: ningún enlace de una
vista previa lleva a uno. Lo que sí tiene página sigue enlazado.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.content.models import (
    ArticleContributor,
    Collection,
    EditorialStatus,
    Page,
    PoemContributor,
    PublishStatus,
)
from apps.people import roles
from apps.people.models import Contributor
from apps.reviews.models import Publisher, Work
from tests.factories import (
    make_article,
    make_event,
    make_image,
    make_poem,
    make_publication,
    make_published_article,
    make_published_poem,
    make_recording,
    publish,
    soup,
)

pytestmark = pytest.mark.django_db
S = EditorialStatus
BANNER = "Vista previa: no publicado"


def _is_preview(response):
    content = response.content.decode()
    return (
        response.status_code == 200
        and BANNER in content
        and '<meta name="robots" content="noindex' in content
        and response.get("X-Robots-Tag") == "noindex"
        and "no-store" in response.get("Cache-Control", "")
    )


@pytest.fixture
def other_author(groups):
    user = get_user_model().objects.create_user("otra_autora", password="pw", is_staff=True)
    user.groups.add(groups[roles.AUTHOR])
    return user


@pytest.mark.parametrize("model", ["article", "poem"])
def test_the_editor_and_the_owner_preview_a_draft_and_nobody_else(
    client, editor, autor, other_author, model
):
    make = make_article if model == "article" else make_poem
    draft = make(owner=autor, status=S.IN_REVIEW)
    url = draft.get_absolute_url()
    assert client.get(url).status_code == 404
    for person in (editor, autor):
        client.force_login(person)
        assert _is_preview(client.get(url)), person
    client.force_login(other_author)
    assert client.get(url).status_code == 404
    # Control: lo publicado se ve igual que siempre, sin franja ni noindex.
    published = make(owner=autor, status=S.PUBLISHED)
    client.force_login(editor)
    response = client.get(published.get_absolute_url())
    assert response.status_code == 200
    assert BANNER not in response.content.decode()
    assert "X-Robots-Tag" not in response


def _unpublished():
    return {
        "registro": make_recording(slug="registro-oculto", published=False),
        "actividad": make_event(slug="actividad-oculta", published=False),
        "publicacion": make_publication(slug="publicacion-oculta", published=False),
        "coleccion": Collection.objects.create(
            slug="coleccion-oculta", title="Colección", status=PublishStatus.DRAFT
        ),
        "pagina": Page.objects.create(
            slug="pagina-oculta", title="Página", body="Texto", status=PublishStatus.DRAFT
        ),
    }


@pytest.mark.parametrize("kind", ["registro", "actividad", "publicacion", "coleccion", "pagina"])
def test_the_editor_previews_what_is_not_published_yet(client, editor, kind):
    url = _unpublished()[kind].get_absolute_url()
    assert client.get(url).status_code == 404
    client.force_login(editor)
    assert _is_preview(client.get(url))


def test_view_on_site_works_for_a_draft(client, editor):
    draft = make_article(status=S.DRAFT, published_at=None)
    client.force_login(editor)
    change = client.get(reverse("admin:content_article_change", args=[draft.pk]))
    assert "/admin/r/" in change.content.decode(), "control: el panel ofrece «Ver en el sitio»"
    content_type = ContentType.objects.get_for_model(draft).pk
    response = client.get(reverse("admin:view_on_site", args=[content_type, draft.pk]), follow=True)
    assert _is_preview(response)


def test_a_scheduled_piece_is_previewed_until_it_is_published(client, editor):
    scheduled = make_article(status=S.SCHEDULED, published_at=timezone.now() + timedelta(days=1))
    client.force_login(editor)
    assert _is_preview(client.get(scheduled.get_absolute_url()))


def test_without_access_to_the_panel_there_is_no_preview(client, groups):
    """Alguien que conserva los permisos de su grupo pero ya no entra al panel no ve borradores."""
    former = get_user_model().objects.create_user("ya-no-entra", password="pw", is_staff=False)
    former.groups.add(groups[roles.EDITOR])
    draft = make_article(status=S.DRAFT)
    client.force_login(former)
    assert client.get(draft.get_absolute_url()).status_code == 404


def _reviewed_works(client, url):
    """Cada obra reseñada de la ficha, como se lee, y adónde llevan sus enlaces."""
    return [
        (" ".join(obra.p.get_text(" ", strip=True).split()), [a["href"] for a in obra.select("a")])
        for obra in soup(client, url).select(".reviewed .obra")
    ]


def test_the_preview_links_the_reviewed_work_only_if_it_has_a_page(client, editor):
    """Una reseña sin publicar puede reseñar una obra que todavía no tiene ficha: la obra y su
    editorial se nombran sin enlace, que llevaría a un 404. La que ya la tiene sigue enlazada."""
    editorial = Publisher.objects.create(slug="editorial-nueva", name="Editorial Nueva")
    nueva = Work.objects.create(
        slug="obra-nueva", title="Obra nueva", publisher=editorial, publication_year=2025
    )
    resenada = Work.objects.create(slug="obra-resenada", title="Obra ya reseñada")
    make_published_article(slug="la-otra-resena").reviewed_works.add(resenada)
    borrador = make_article(slug="resena-en-borrador", status=S.IN_REVIEW)
    borrador.reviewed_works.add(nueva, resenada)
    # Lo que no tiene ficha responde 404.
    assert client.get(nueva.get_absolute_url()).status_code == 404
    assert client.get(editorial.get_absolute_url()).status_code == 404

    client.force_login(editor)
    url = borrador.get_absolute_url()
    assert _is_preview(client.get(url))
    assert _reviewed_works(client, url) == [
        ("Obra nueva Editorial Nueva · 2025", []),
        ("Obra ya reseñada", [resenada.get_absolute_url()]),
    ]
    # Al publicarse, la reseña le da ficha a la obra y a su editorial, y la ficha las enlaza.
    publish(borrador)
    assert _reviewed_works(client, url)[0] == (
        "Obra nueva Editorial Nueva · 2025",
        [nueva.get_absolute_url(), editorial.get_absolute_url()],
    )
    assert client.get(nueva.get_absolute_url()).status_code == 200


@pytest.fixture
def signers():
    """Quien firma sin nada publicado, que no tiene página, y dos que la tienen por razones
    distintas: alguien de fuera que firma un poema publicado y una integrante sin nada publicado."""
    berta = Contributor.objects.create(slug="berta", display_name="Berta Invitada")
    luis = Contributor.objects.create(slug="luis", display_name="Luis Mora")
    PoemContributor.objects.create(poem=make_published_poem(), contributor=luis)
    ana = Contributor.objects.create(slug="ana", display_name="Ana Pizarro", is_member=True)
    return berta, luis, ana


def _sign(piece, people):
    """Las firmas de un texto o de un poema, en ese orden."""
    model = type(piece).__name__.lower()
    bridge = ArticleContributor if model == "article" else PoemContributor
    for position, person in enumerate(people):
        bridge.objects.create(**{model: piece}, contributor=person, position=position)


def _named(names):
    """Cada nombre, como se lee, y adónde lleva: None si se nombra sin enlace."""
    return [(name.get_text(), name.get("href")) for name in names]


def _signatures(sopa):
    """Quienes firman, bajo el título."""
    return _named(sopa.select(".lectura-firmas li > a, .lectura-firmas li > .sin-enlace"))


def _doors(sopa, rotulo):
    """Las puertas del pie con ese rótulo."""
    return _named(
        name
        for li in sopa.select("nav.pie-entidad li")
        if li.select_one(".rotulo").get_text() == rotulo
        for name in li.select(":scope > a, :scope > .sin-enlace")
    )


def _walk(client, sopa):
    """Cada enlace interno de la página, pedido por quien la ve como al pulsarlo (sin el
    fragmento), y su código."""
    links = {
        a["href"].split("#")[0]
        for a in sopa.select('a[href^="/"]')
        if not a["href"].startswith("//")
    }
    return {href: client.get(href).status_code for href in sorted(links)}


def _not_200(codes):
    return {href: code for href, code in codes.items() if code != 200}


@pytest.mark.parametrize("make", [make_article, make_poem])
def test_the_preview_names_a_signer_without_a_page_without_a_link(
    client, editor, signers, legal_pages, make
):
    """Quien firma un texto o un poema sin publicar y no tiene nada publicado no tiene página: la
    vista previa la nombra sin enlace, en las firmas y en el pie. Quien la tiene sigue enlazado."""
    berta, luis, ana = signers
    borrador = make(status=S.IN_REVIEW)
    _sign(borrador, signers)
    # La página de Berta responde 404; las de los otros dos, 200.
    assert client.get(berta.get_absolute_url()).status_code == 404
    assert [client.get(c.get_absolute_url()).status_code for c in (luis, ana)] == [200, 200]

    client.force_login(editor)
    url = borrador.get_absolute_url()
    assert _is_preview(client.get(url))
    sopa = soup(client, url)
    named = [
        ("Berta Invitada", None),
        ("Luis Mora", luis.get_absolute_url()),
        ("Ana Pizarro", ana.get_absolute_url()),
    ]
    assert _signatures(sopa) == named
    assert _doors(sopa, "Más de") == named
    # Ningún enlace de la página lleva a un 404. Control: el recorrido pasa por las páginas de
    # quienes firman con página.
    codes = _walk(client, sopa)
    assert {luis.get_absolute_url(), ana.get_absolute_url()} <= codes.keys()
    assert _not_200(codes) == {}
    # Al publicarse, la pieza le da página a quien la firma, y la ficha la enlaza.
    publish(borrador)
    assert _signatures(soup(client, url))[0] == ("Berta Invitada", berta.get_absolute_url())
    assert client.get(berta.get_absolute_url()).status_code == 200


def _meta(sopa):
    """Los datos de la publicación bajo su título, como se leen, y adónde llevan sus enlaces."""
    meta = sopa.select_one(".pub-detail .meta")
    return " ".join(meta.get_text(" ", strip=True).split()), [a["href"] for a in meta.select("a")]


def test_the_preview_of_a_publication_links_its_publisher_only_if_it_has_a_page(
    client, editor, signers, legal_pages
):
    """La editorial de una publicación sin publicar puede no tener nada publicado: la vista previa
    la nombra sin enlace, en los datos y en el pie. La que tiene página sigue enlazada."""
    berta, luis, _ = signers
    nueva = Publisher.objects.create(slug="editorial-nueva", name="Editorial Nueva")
    conocida = Publisher.objects.create(slug="editorial-conocida", name="Editorial Conocida")
    make_publication(publisher=conocida)  # publicada: le da página a su editorial
    assert client.get(nueva.get_absolute_url()).status_code == 404
    assert client.get(conocida.get_absolute_url()).status_code == 200

    client.force_login(editor)
    for editorial, href in ((nueva, None), (conocida, conocida.get_absolute_url())):
        borrador = make_publication(publisher=editorial, published=False, year=2025)
        borrador.participants.add(berta, luis)
        url = borrador.get_absolute_url()
        assert _is_preview(client.get(url))
        sopa = soup(client, url)
        assert _meta(sopa) == (f"2025 · {editorial.name}", [href] if href else [])
        assert _doors(sopa, "Editorial") == [(editorial.name, href)]
        # Control en la misma respuesta: la puerta de quien participa con página va enlazada.
        assert _doors(sopa, "Más de") == [("Luis Mora", luis.get_absolute_url())]
        codes = _walk(client, sopa)
        assert luis.get_absolute_url() in codes
        assert _not_200(codes) == {}


@pytest.mark.parametrize("make", [make_article, make_poem])
def test_the_preview_costs_the_same_queries_with_five_signers_as_with_one(client, editor, make):
    """Saber quién tiene página no cuesta una consulta por persona: llega con las firmas y sus
    retratos, en las mismas consultas para una que para cinco."""
    people = [
        Contributor.objects.create(
            slug=f"firma-{n}",
            display_name=f"Firma {n}",
            is_member=n % 2 == 1,
            photo=make_image(f"retrato-{n}"),
        )
        for n in range(5)
    ]
    borrador = make(status=S.IN_REVIEW)
    _sign(borrador, people[:1])
    client.force_login(editor)
    url = borrador.get_absolute_url()
    soup(client, url)  # en caliente: el perfil del sitio ya existe
    with CaptureQueriesContext(connection) as una:
        soup(client, url)
    borrador.authors.clear()
    _sign(borrador, people)
    with CaptureQueriesContext(connection) as cinco:
        sopa = soup(client, url)
    # Control: la vista previa nombra a las cinco, cada una con su retrato, y enlaza a quien tiene
    # página.
    assert _signatures(sopa) == [
        (p.display_name, p.get_absolute_url() if p.is_member else None) for p in people
    ]
    assert len(sopa.select(".lectura-firmas img")) == 5
    assert len(cinco) == len(una), "una consulta más por persona"
