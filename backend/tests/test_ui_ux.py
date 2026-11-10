"""UX y accesibilidad: skip link, buscador overlay, focus, lightbox (Lote UI-3)."""

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from apps.content.models import (
    ArticleContributor,
    Collection,
    CollectionArticle,
    CollectionPoem,
    PoemContributor,
    PublishStatus,
    Section,
    Tag,
)
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from tests import css
from tests.factories import (
    make_event,
    make_photo,
    make_publication,
    make_published_article,
    make_published_poem,
    soup,
)

pytestmark = pytest.mark.django_db


def test_skip_link_and_main_landmark(client):
    content = client.get(reverse("content:text_archive")).content
    assert b'class="skip" href="#main"' in content
    # El destino del enlace de salto: un <main> con ese id. (Antes se afirmaba además la
    # clase `wrap`; <main> dejó de ser la caja de 820 px al pasar a ser el lienzo.)
    assert b'<main id="main" class="lienzo' in content
    # En la portada salta también la obra (D18): lleva a la hoja, que está dentro de <main>.
    portada = client.get(reverse("site:home")).content.decode()
    assert 'class="skip" href="#contenido"' in portada
    assert portada.index('<main id="main"') < portada.index('id="contenido"')


def test_the_search_panel_announces_a_count_and_not_the_whole_list(client):
    """Los resultados no son una región viva: el lector los leería enteros en cada pausa. Se
    anuncia el recuento, en una región de estado aparte que rellena la parcial (test_search)."""
    sopa = BeautifulSoup(client.get(reverse("site:home")).content, "html.parser")
    # Un solo contenedor de resultados (el div suelto a ancho completo desapareció).
    resultados = sopa.select("#search-results")
    assert len(resultados) == 1
    assert resultados[0].find_parent(attrs={"aria-live": True}) is None
    assert not resultados[0].has_attr("aria-live")
    estado = sopa.select(".busqueda #search-status")
    assert len(estado) == 1 and estado[0]["role"] == "status"
    assert "sr-only" in estado[0]["class"] and estado[0].get_text() == ""


def test_css_has_focus_visible_overlay_and_lightbox():
    """El foco se ve en todo lo que se enfoca; el salto al contenido espera fuera de la vista
    hasta recibir el foco; los resultados flotan sobre la página, y la vista ampliada sin
    JavaScript se abre con su ancla."""
    (foco,) = css.rules_with((), "a:focus-visible")
    assert foco["outline"] == "2px solid var(--accent)"
    salto = css.rule((), ".skip")
    assert salto["position"] == "absolute" and salto["top"].startswith("-")
    assert not css.rule((), ".skip:focus")["top"].startswith("-")
    assert css.rule((), ".busqueda-resultados")["position"] == "absolute"
    assert css.rule((), ".lightbox")["display"] == "none"
    assert css.rule((), ".lightbox:target")["display"] == "grid"


def test_event_gallery_renders_lightbox(client):
    event = make_event(slug="con-lightbox", title="Evento Lightbox")
    make_photo(event)
    resp = client.get(reverse("agenda:event_detail", args=[event.slug]))
    assert resp.status_code == 200
    assert b'class="lightbox"' in resp.content
    assert b"#lb-con-lightbox-1" in resp.content  # el thumbnail enlaza al overlay
    assert b'href="#galeria-con-lightbox"' in resp.content  # y el overlay cierra a la sección
    # Vista ampliada honesta: no promete semántica de modal (sin trampa de foco).
    assert b"aria-modal" not in resp.content
    assert b'role="dialog"' not in resp.content


def test_home_has_an_h1(client):
    # La portada (la página más enlazada) debe tener su <h1> (SEO + encabezados a11y).
    resp = client.get(reverse("site:home"))
    assert b"<h1" in resp.content


def test_card_titles_sit_one_level_below_the_heading_they_hang_from(client):
    """Quien recorre una página por sus encabezados no se salta ningún nivel: bajo el h1 de un
    índice, el título de cada tarjeta es un h2; bajo el h2 de una sección (los textos de una
    integrante, las reseñas de una obra, la obra de la portada), un h3."""
    section = Section.objects.create(slug="cronica", name="Crónica")
    tag = Tag.objects.create(slug="ciudad", name="Ciudad")
    member = Contributor.objects.create(
        slug="integrante", display_name="Integrante", is_member=True
    )
    guest = Contributor.objects.create(slug="invitada", display_name="Invitada")
    publisher = Publisher.objects.create(slug="editorial", name="Editorial")
    author = BookAuthor.objects.create(slug="autora", name="Autora")
    book = make_publication(slug="libro", title="Libro")
    work = Work.objects.create(slug="obra", title="Obra", publisher=publisher, publicacion=book)
    work.authors.add(author)
    collection = Collection.objects.create(
        slug="coleccion", title="Colección", status=PublishStatus.PUBLISHED
    )
    for person in (member, guest):
        article = make_published_article(slug=f"texto-{person.slug}", section=section)
        article.tags.add(tag)
        article.reviewed_works.add(work)
        ArticleContributor.objects.create(article=article, contributor=person)
        poem = make_published_poem(slug=f"poema-{person.slug}")
        PoemContributor.objects.create(poem=poem, contributor=person)
        CollectionArticle.objects.create(collection=collection, article=article)
        CollectionPoem.objects.create(collection=collection, poem=poem, position=1)

    pages = [
        reverse("content:text_archive"),
        reverse("content:poem_index"),
        section.get_absolute_url(),
        tag.get_absolute_url(),
        collection.get_absolute_url(),
        member.get_absolute_url(),
        guest.get_absolute_url(),
        work.get_absolute_url(),
        publisher.get_absolute_url(),
        author.get_absolute_url(),
        book.get_absolute_url(),
        reverse("site:home"),
    ]
    levels = {f"h{n}": n for n in range(1, 7)}
    for url in pages:
        headings = soup(client, url).select("main :is(h1, h2, h3, h4, h5, h6)")
        cards = [h for h in headings if h.find_parent("li", class_="article-card")]
        assert cards, f"control: {url} no enseña ninguna tarjeta"
        for card in cards:
            above = [h for h in headings[: headings.index(card)] if h not in cards]
            assert levels[card.name] == levels[above[-1].name] + 1, (
                f"en {url}, «{card.get_text(strip=True)}» es un {card.name} bajo el "
                f"{above[-1].name} «{above[-1].get_text(strip=True)}»"
            )


def test_submit_file_help_aria_reference_resolves(client):
    """El aria-describedby del input de archivo apunta a un id que EXISTE en el
    documento (antes la referencia ARIA estaba rota, #14). Verificado con bs4."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(client.get(reverse("submissions:submit")).content, "html.parser")
    file_input = soup.find("input", {"type": "file"})
    described_by = file_input.get("aria-describedby")
    assert described_by, "el input de archivo debe declarar aria-describedby"
    assert soup.find(id=described_by) is not None, f"id '{described_by}' no existe en el HTML"
