"""Lo que no está publicado no aparece en ninguna superficie pública.

Una matriz: cada estado no público de Article y Poem, y `published=False` (el borrador o, en los
aliados, `active=False`) en lo demás, contra cada página, feed y mapa del sitio que lista o enlaza esas piezas. Cada caso lleva
su control en la misma prueba: una pieza publicada que la superficie sí enseña, porque una prueba
de «no aparece» sin él pasaría también mirando una página vacía.

La pieza oculta es siempre la que se colaría primero si faltara el filtro: la más reciente, la
más próxima o la primera de la lista. En Article y Poem lleva además una fecha de publicación
pasada, como lo despublicado y lo archivado, así que un filtro por fecha en vez de por estado
también falla aquí.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.agenda.services import stats
from apps.content.models import (
    Article,
    ArticleContributor,
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialStatus,
    Page,
    Poem,
    PoemContributor,
    PublishStatus,
    ReviewedWork,
    Section,
    Tag,
)
from apps.content.services import ultima_publicacion
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from apps.showcase.models import Partner, PressMention, SiteProfile
from tests.factories import make_event, make_photo, make_publication, make_recording

pytestmark = pytest.mark.django_db

S = EditorialStatus
HIDDEN_STATES = [status for status in S.values if status != S.PUBLISHED]


def _shows(content, item):
    """La respuesta enseña la pieza: su dirección, su título (o su nombre, si es una persona o
    un aliado) o, en la prensa, su cita."""
    url = item.get_absolute_url() if hasattr(item, "get_absolute_url") else None
    marks = [getattr(item, name, "") for name in ("title", "display_name", "name", "quote")]
    return bool(url and url in content) or any(mark and mark in content for mark in marks)


def _check(client, views, hidden):
    """Cada vista es (url, controles): los controles se ven y lo oculto no, en ninguna."""
    controls = 0
    for url, expected in views:
        response = client.get(url)
        assert response.status_code == 200, url
        content = response.content.decode()
        for item in expected:
            assert _shows(content, item), f"{url} no enseña el control «{item.title}»"
            controls += 1
        for item in hidden:
            assert not _shows(content, item), f"{url} enseña «{item.title}», que está oculta"
    assert controls, "la superficie no tiene control"


def _member():
    return Contributor.objects.create(
        slug="integrante", display_name="La Integrante", is_member=True
    )


# ── Article y Poem ───────────────────────────────────────────────────────────────────────────


def _editorial_world(model, hidden_status):
    """Tres piezas con las mismas relaciones: la oculta (la más reciente), una publicada que hace
    de control y otra publicada, que además es la vecina de la de control en su ficha. Firma
    también la oculta, y solo esa, una colaboradora que entonces no tiene nada publicado."""
    w = SimpleNamespace(member=_member())
    w.guest = Contributor.objects.create(slug="firma-visible", display_name="Firma visible")
    w.hidden_guest = Contributor.objects.create(
        slug="firma-escondida", display_name="Firma escondida"
    )
    w.section = Section.objects.create(slug="seccion", name="Una sección")
    w.tag = Tag.objects.create(slug="etiqueta", name="Una etiqueta")
    w.collection = Collection.objects.create(
        slug="coleccion", title="Una colección", status=PublishStatus.PUBLISHED
    )
    w.publication = make_publication(slug="publicacion", title="Una publicación")
    w.publisher = Publisher.objects.create(slug="editorial", name="Una editorial")
    w.book_author = BookAuthor.objects.create(slug="autora-de-obra", name="Una autora de obra")
    w.work = Work.objects.create(
        slug="obra", title="Una obra", publisher=w.publisher, publicacion=w.publication
    )
    w.work.authors.add(w.book_author)
    now = timezone.now()
    # El registro es el más antiguo, para que la última publicación sea una de las piezas.
    w.recording = make_recording(
        slug="registro", title="Un registro", featured=True, published_at=now - timedelta(days=9)
    )
    for days, key, status, label in (
        (1, "hidden", hidden_status, "oculta"),
        (2, "shown", S.PUBLISHED, "visible"),
        (3, "other", S.PUBLISHED, "vecina"),
    ):
        title = f"Zarzamora {label}"
        fields = {
            "slug": f"zarzamora-{label}",
            "title": title,
            "status": status,
            "published_at": now - timedelta(days=days),
        }
        if model is Article:
            piece = Article.objects.create(
                body=f"{title}. " + "palabra " * 60, section=w.section, **fields
            )
            ArticleContributor.objects.create(article=piece, contributor=w.member, position=0)
            ArticleContributor.objects.create(article=piece, contributor=w.guest, position=1)
            piece.tags.add(w.tag)
            ReviewedWork.objects.create(article=piece, work=w.work)
            CollectionArticle.objects.create(collection=w.collection, article=piece)
            if key == "hidden":
                ArticleContributor.objects.create(
                    article=piece, contributor=w.hidden_guest, position=2
                )
        else:
            # El primer verso lleva el título: la tirada de la portada enseña solo ese verso.
            piece = Poem.objects.create(
                body=f"{title} en el primer verso\nY un verso más", recording=w.recording, **fields
            )
            PoemContributor.objects.create(poem=piece, contributor=w.member)
            CollectionPoem.objects.create(collection=w.collection, poem=piece)
            signer = {"hidden": w.hidden_guest, "shown": w.guest}.get(key)
            if signer:
                PoemContributor.objects.create(poem=piece, contributor=signer, position=1)
        setattr(w, key, piece)
    w.hidden_items = [w.hidden, w.hidden_guest]
    return w


ARTICLE_SURFACES = {
    "portada": lambda w: [(reverse("content:home"), [w.other])],
    "archivo de textos": lambda w: [(reverse("content:text_archive"), [w.other])],
    "sección": lambda w: [(reverse("content:section_detail", args=[w.section.slug]), [w.other])],
    "etiqueta": lambda w: [(reverse("content:tag_detail", args=[w.tag.slug]), [w.other])],
    "búsqueda": lambda w: [(reverse("content:search") + "?q=zarzamora", [w.other])],
    "búsqueda por firma": lambda w: [(reverse("content:search") + "?q=firma", [w.guest])],
    "RSS": lambda w: [(reverse("feed"), [w.other])],
    "sitemap": lambda w: [(reverse("sitemap"), [w.other])],
    "ficha de integrante": lambda w: [
        (reverse("people:member_detail", args=[w.member.slug]), [w.other])
    ],
    "ficha de colaboradora": lambda w: [
        (reverse("content:contributor_detail", args=[w.guest.slug]), [w.other])
    ],
    "colección": lambda w: [(w.collection.get_absolute_url(), [w.other])],
    "obra": lambda w: [(reverse("reviews:work_detail", args=[w.work.slug]), [w.other])],
    "editorial": lambda w: [
        (reverse("reviews:publisher_detail", args=[w.publisher.slug]), [w.other])
    ],
    "autora de obra": lambda w: [
        (reverse("reviews:bookauthor_detail", args=[w.book_author.slug]), [w.other])
    ],
    "publicación reseñada": lambda w: [(w.publication.get_absolute_url(), [w.other])],
    "ficha vecina": lambda w: [(w.shown.get_absolute_url(), [w.other])],
}

POEM_SURFACES = {
    "portada": lambda w: [(reverse("content:home"), [w.other])],
    "índice de poemas": lambda w: [(reverse("content:poem_index"), [w.other])],
    "búsqueda": lambda w: [(reverse("content:search") + "?q=zarzamora", [w.other])],
    "búsqueda por firma": lambda w: [(reverse("content:search") + "?q=firma", [w.guest])],
    "sitemap": lambda w: [(reverse("sitemap"), [w.other])],
    "ficha de integrante": lambda w: [
        (reverse("people:member_detail", args=[w.member.slug]), [w.other])
    ],
    "colección": lambda w: [(w.collection.get_absolute_url(), [w.other])],
    "ficha del registro": lambda w: [(w.recording.get_absolute_url(), [w.other])],
    "ficha vecina": lambda w: [(w.shown.get_absolute_url(), [w.other])],
}


@pytest.mark.parametrize("surface", ARTICLE_SURFACES)
@pytest.mark.parametrize("status", HIDDEN_STATES)
def test_a_hidden_article_stays_off_every_surface(client, status, surface):
    w = _editorial_world(Article, status)
    _check(client, ARTICLE_SURFACES[surface](w), w.hidden_items)


@pytest.mark.parametrize("surface", POEM_SURFACES)
@pytest.mark.parametrize("status", HIDDEN_STATES)
def test_a_hidden_poem_stays_off_every_surface(client, status, surface):
    w = _editorial_world(Poem, status)
    _check(client, POEM_SURFACES[surface](w), w.hidden_items)


@pytest.mark.parametrize("model", [Article, Poem], ids=["article", "poem"])
@pytest.mark.parametrize("status", HIDDEN_STATES)
def test_a_hidden_piece_has_no_page(client, model, status):
    w = _editorial_world(model, status)
    assert client.get(w.other.get_absolute_url()).status_code == 200
    assert client.get(w.hidden.get_absolute_url()).status_code == 404


@pytest.mark.parametrize("status", HIDDEN_STATES)
def test_the_home_features_a_poem_only_if_it_is_published(client, status):
    w = _editorial_world(Poem, status)
    # Sin registros destacados, la portada destaca el poema del perfil.
    w.recording.featured = False
    w.recording.save(update_fields=["featured"])
    profile = SiteProfile.load()
    profile.featured_poem = w.shown
    profile.save()
    assert 'class="home-block featured"' in client.get("/").content.decode()
    profile.featured_poem = w.hidden
    profile.save()
    content = client.get("/").content.decode()
    assert 'class="home-block featured"' not in content
    assert not _shows(content, w.hidden)


@pytest.mark.parametrize("model", [Article, Poem], ids=["article", "poem"])
@pytest.mark.parametrize("status", HIDDEN_STATES)
def test_the_last_publication_date_skips_hidden_pieces(model, status):
    """El «Actualizado el…» de la portada y del dossier."""
    w = _editorial_world(model, status)
    assert ultima_publicacion() == w.shown.published_at


# ── Lo que se publica con una casilla o con dos estados ──────────────────────────────────────


def _event_world():
    """Tres actividades por venir y tres pasadas: en cada grupo, la oculta es la más cercana a
    hoy. Las pasadas tienen foto, para la galería."""
    w = SimpleNamespace(member=_member())
    now = timezone.now()
    for days, key, label in (
        (1, "hidden", "oculta"),
        (2, "shown", "visible"),
        (3, "other", "vecina"),
    ):
        for when, sign in (("future", 1), ("past", -1)):
            event = make_event(
                slug=f"actividad-{label}-{when}",
                title=f"Actividad {label} {'futura' if sign > 0 else 'pasada'}",
                starts_at=now + sign * timedelta(days=days),
                published=key != "hidden",
            )
            event.participants.add(w.member)
            if sign < 0:
                make_photo(event)
            setattr(w, f"{key}_{when}", event)
    w.hidden = [w.hidden_future, w.hidden_past]
    return w


def _recording_world():
    w = SimpleNamespace(member=_member())
    w.event = make_event(slug="actividad", title="Una actividad", published=True)
    now = timezone.now()
    for position, key, label in (
        (0, "hidden", "oculto"),
        (1, "shown", "visible"),
        (2, "other", "vecino"),
    ):
        recording = make_recording(
            slug=f"registro-{label}",
            title=f"Registro {label}",
            kind=Recording.Kind.AUDIO,
            featured=True,
            published=key != "hidden",
            position=position,
            event=w.event,
            published_at=now - timedelta(days=position + 1),
        )
        recording.participants.add(w.member)
        setattr(w, key, recording)
    # Dos poemas publicados: uno se lee en el registro oculto y otro en el vecino.
    for key, recording in (("poem_of_hidden", w.hidden), ("poem_of_other", w.other)):
        poem = Poem.objects.create(
            slug=key.replace("_", "-"),
            title=f"Poema {key}",
            body="Un verso",
            status=S.PUBLISHED,
            published_at=now - timedelta(days=9),
            recording=recording,
        )
        setattr(w, key, poem)
    w.hidden = [w.hidden]
    return w


def _publication_world():
    w = SimpleNamespace()
    for position, key, label in (
        (0, "hidden", "oculta"),
        (1, "shown", "visible"),
        (2, "other", "vecina"),
    ):
        publication = make_publication(
            slug=f"publicacion-{label}",
            title=f"Publicación {label}",
            featured=True,
            published=key != "hidden",
            position=position,
            year=2024 - position,
        )
        setattr(w, key, publication)
    # Dos obras del catálogo: una es la publicación oculta y otra la vecina.
    w.work_of_hidden = Work.objects.create(slug="obra-oculta", title="Obra", publicacion=w.hidden)
    w.work_of_other = Work.objects.create(slug="obra-vecina", title="Obra", publicacion=w.other)
    # La obra de la publicación oculta tiene ficha por una reseña publicada: la ficha existe, y
    # aun así no puede enseñar la publicación.
    review = Article.objects.create(
        slug="resena-de-la-obra", title="Reseña", body="Texto", status=S.PUBLISHED,
        published_at=timezone.now(),
    )  # fmt: skip
    ReviewedWork.objects.create(article=review, work=w.work_of_hidden)
    w.hidden = [w.hidden]
    return w


def _page_world():
    w = SimpleNamespace()
    for key, label, status in (
        ("hidden", "oculta", PublishStatus.DRAFT),
        ("shown", "visible", PublishStatus.PUBLISHED),
        ("other", "vecina", PublishStatus.PUBLISHED),
    ):
        page = Page.objects.create(
            slug=f"pagina-{label}", title=f"Página {label}", body="Texto", status=status
        )
        setattr(w, key, page)
    w.hidden = [w.hidden]
    return w


def _collection_world():
    w = SimpleNamespace()
    w.poem = Poem.objects.create(
        slug="poema", title="Un poema", body="Un verso", status=S.PUBLISHED,
        published_at=timezone.now(),
    )  # fmt: skip
    for key, label, status in (
        ("hidden", "oculta", PublishStatus.DRAFT),
        ("shown", "visible", PublishStatus.PUBLISHED),
        ("other", "vecina", PublishStatus.PUBLISHED),
    ):
        collection = Collection.objects.create(
            slug=f"coleccion-{label}", title=f"Colección {label}", status=status
        )
        CollectionPoem.objects.create(collection=collection, poem=w.poem)
        setattr(w, key, collection)
    w.hidden = [w.hidden]
    return w


def _press_world():
    w = SimpleNamespace()
    for position, key, label in (
        (0, "hidden", "oculta"),
        (1, "shown", "visible"),
        (2, "other", "vecina"),
    ):
        mention = PressMention.objects.create(
            title=f"Mención {label}",
            outlet="Gaceta de Prueba",
            quote=f"Una cita {label}",
            published=key != "hidden",
            position=position,
        )
        setattr(w, key, mention)
    w.hidden = [w.hidden]
    return w


def _partner_world():
    w = SimpleNamespace()
    for position, key, label in (
        (0, "hidden", "oculto"),
        (1, "shown", "visible"),
        (2, "other", "vecino"),
    ):
        partner = Partner.objects.create(
            name=f"Aliado {label}", active=key != "hidden", position=position
        )
        setattr(w, key, partner)
    w.hidden = [w.hidden]
    return w


EVENT_SURFACES = {
    "agenda": lambda w: [(reverse("agenda:agenda"), [w.other_future])],
    "búsqueda": lambda w: [(reverse("content:search") + "?q=actividad", [w.other_future])],
    "portada": lambda w: [("/", [w.shown_future, w.shown_past])],
    "trayectoria": lambda w: [(reverse("agenda:trayectoria"), [w.other_past])],
    "galería": lambda w: [(reverse("agenda:gallery"), [w.other_past])],
    "dossier": lambda w: [(reverse("showcase:dossier"), [w.other_past])],
    "sitemap": lambda w: [(reverse("sitemap"), [w.other_future])],
    "ficha de integrante": lambda w: [
        (reverse("people:member_detail", args=[w.member.slug]), [w.other_past])
    ],
    "ficha vecina": lambda w: [(w.shown_future.get_absolute_url(), [w.other_future])],
}

RECORDING_SURFACES = {
    "índice de registros": lambda w: [(reverse("media:recording_index"), [w.other])],
    "búsqueda": lambda w: [(reverse("content:search") + "?q=registro", [w.other])],
    "portada": lambda w: [("/", [w.other])],
    "pódcast": lambda w: [(reverse("recordings_feed"), [w.other])],
    "sitemap": lambda w: [(reverse("sitemap"), [w.other])],
    "ficha de integrante": lambda w: [
        (reverse("people:member_detail", args=[w.member.slug]), [w.other])
    ],
    "ficha de la actividad": lambda w: [(w.event.get_absolute_url(), [w.other])],
    "ficha vecina": lambda w: [(w.shown.get_absolute_url(), [w.other])],
    "ficha del poema": lambda w: [
        (w.poem_of_hidden.get_absolute_url(), []),
        (w.poem_of_other.get_absolute_url(), [w.other]),
    ],
}

PUBLICATION_SURFACES = {
    "catálogo": lambda w: [(reverse("showcase:publication_index"), [w.other])],
    "búsqueda": lambda w: [(reverse("content:search") + "?q=publicacion", [w.other])],
    "portada": lambda w: [("/", [w.other])],
    "dossier": lambda w: [(reverse("showcase:dossier"), [w.other])],
    "trayectoria": lambda w: [(reverse("agenda:trayectoria"), [w.other])],
    "sitemap": lambda w: [(reverse("sitemap"), [w.other])],
    "ficha vecina": lambda w: [(w.shown.get_absolute_url(), [w.other])],
    "ficha de la obra": lambda w: [
        (reverse("reviews:work_detail", args=[w.work_of_hidden.slug]), []),
        (reverse("reviews:work_detail", args=[w.work_of_other.slug]), [w.other]),
    ],
}

PAGE_SURFACES = {
    "sitemap": lambda w: [(reverse("sitemap"), [w.other])],
}

COLLECTION_SURFACES = {
    "índice de colecciones": lambda w: [(reverse("content:collection_index"), [w.other])],
    "sitemap": lambda w: [(reverse("sitemap"), [w.other])],
    "ficha del poema": lambda w: [(w.poem.get_absolute_url(), [w.other])],
}

PRESS_SURFACES = {
    "prensa": lambda w: [(reverse("showcase:press_index"), [w.other])],
    "dossier": lambda w: [(reverse("showcase:dossier"), [w.other])],
}

PARTNER_SURFACES = {
    "aliados": lambda w: [(reverse("showcase:partner_index"), [w.other])],
    "dossier": lambda w: [(reverse("showcase:dossier"), [w.other])],
}

WORLDS = {
    "Event": (_event_world, EVENT_SURFACES),
    "Recording": (_recording_world, RECORDING_SURFACES),
    "Publication": (_publication_world, PUBLICATION_SURFACES),
    "Page": (_page_world, PAGE_SURFACES),
    "Collection": (_collection_world, COLLECTION_SURFACES),
    "PressMention": (_press_world, PRESS_SURFACES),
    "Partner": (_partner_world, PARTNER_SURFACES),
}


@pytest.mark.parametrize(
    ("model", "surface"),
    [(model, surface) for model, (_, surfaces) in WORLDS.items() for surface in surfaces],
)
def test_an_unpublished_object_stays_off_every_surface(client, model, surface):
    build, surfaces = WORLDS[model]
    w = build()
    _check(client, surfaces[surface](w), w.hidden)


@pytest.mark.parametrize("model", ["Event", "Recording", "Publication", "Page", "Collection"])
def test_an_unpublished_object_has_no_page(client, model):
    w = WORLDS[model][0]()
    other = w.other_future if model == "Event" else w.other
    assert client.get(other.get_absolute_url()).status_code == 200
    for hidden in w.hidden:
        assert client.get(hidden.get_absolute_url()).status_code == 404


def test_the_trajectory_numbers_count_only_what_is_published():
    """Las cifras de /trayectoria/ y del dossier: actividades pasadas y publicaciones."""
    events = _event_world()
    _publication_world()
    numbers = stats()
    assert numbers["events"] == 2, events.hidden_past
    assert numbers["publications"] == 2


def test_the_last_publication_date_skips_hidden_recordings():
    w = _recording_world()
    assert ultima_publicacion() == w.shown.published_at
