"""Toda ficha pública sabe decir dónde vive.

El modelo de cada ruta de ficha tiene `get_absolute_url`, y las plantillas, los sitemaps, los
feeds y la búsqueda lo usan en vez de componer la dirección con el nombre de la ruta. Sin el
método, el panel no ofrece «Ver en el sitio» y quien acaba de publicar tiene que componer la
dirección de memoria, que falla: el slug de un artículo se deriva de la obra reseñada, no de su
título. Y cada sitio que compone la dirección repite la ruta.

Las rutas públicas, además, son permanentes: la lista congelada del final falla si una deja de
resolver.
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.template.base import Lexer, TokenType
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, resolve, reverse
from django.utils import timezone

from apps.agenda.models import Event
from apps.content.models import (
    LEGAL_PAGES,
    Article,
    Collection,
    EditorialStatus,
    Page,
    Poem,
    PublishStatus,
    Section,
    Tag,
)
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from apps.showcase.models import Publication
from tests.factories import make_article, make_published_article, soup
from tests.test_completeness import ENTITY, ROUTES

pytestmark = pytest.mark.django_db


def _articulo(**extra):
    return Article.objects.create(
        title="Un texto",
        slug="un-texto",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        **extra,
    )


def test_las_tres_urls_apuntan_a_su_ruta():
    a = _articulo()
    c = Collection.objects.create(title="Una colección", slug="una-coleccion")
    p = Page.objects.create(title="Una página", slug="una-pagina")
    assert a.get_absolute_url() == "/texto/un-texto/"
    assert c.get_absolute_url() == "/coleccion/una-coleccion/"
    assert p.get_absolute_url() == "/pagina/una-pagina/"


def test_la_url_lleva_de_verdad_a_la_pieza():
    """Que devuelva una cadena con buena pinta no basta: tiene que resolver."""
    a = _articulo()
    respuesta = Client().get(a.get_absolute_url())
    assert respuesta.status_code == 200
    assert "Un texto" in respuesta.content.decode()


def test_el_panel_ofrece_ver_en_el_sitio():
    """El motivo del arreglo. Django solo pone el botón si el modelo sabe su URL.

    No devuelve la URL directa sino su ruta de redirección `/admin/r/<tipo>/<id>/`, que
    resuelve con `get_absolute_url`. Sin el método, `get_view_on_site_url` da None y el
    botón no se dibuja; por eso se comprueba el enlace Y a dónde lleva.
    """
    from apps.content.admin import ArticleAdmin

    admin_obj = ArticleAdmin(Article, AdminSite())
    a = _articulo()

    enlace = admin_obj.get_view_on_site_url(a)
    assert enlace is not None, "sin enlace no hay botón «Ver en el sitio»"
    assert enlace.startswith("/admin/r/")
    assert admin_obj.get_view_on_site_url(None) is None  # ficha nueva: no hay dónde ir

    # La cadena completa: el botón lleva de verdad a la pieza publicada. La vista de
    # redirección del admin exige sesión de staff, igual que en uso real.
    from django.contrib.auth import get_user_model

    navegador = Client()
    navegador.force_login(
        get_user_model().objects.create_user(username="editor-prueba", password="x", is_staff=True)
    )
    respuesta = navegador.get(enlace)
    assert respuesta.status_code == 302
    # La vista de atajo devuelve una URI absoluta (http://testserver/...).
    assert respuesta["Location"].endswith("/texto/un-texto/")


@pytest.mark.parametrize("borrador", [True, False])
def test_tambien_para_las_piezas_sin_publicar(borrador):
    """La URL existe siempre; que la página responda 404 en borrador es otra capa.

    Es deliberado: el editor necesita el enlace para comprobar cómo quedará, y el filtro
    por estado vive en la vista, no en el modelo.
    """
    a = Article.objects.create(
        title="Otro",
        slug="otro",
        status=EditorialStatus.DRAFT if borrador else EditorialStatus.PUBLISHED,
        published_at=None if borrador else timezone.now(),
    )
    assert a.get_absolute_url() == "/texto/otro/"
    esperado = 404 if borrador else 200
    assert Client().get(a.get_absolute_url()).status_code == esperado


def test_el_sitemap_sigue_respondiendo():
    """Contra-prueba: los sitemaps resolvían con reverse(); añadir el método no los rompe."""
    _articulo()
    Page.objects.create(title="P", slug="p", status=PublishStatus.PUBLISHED)
    assert Client().get("/sitemap.xml").status_code == 200


# La pieza de cada ficha pública, con lo que la distingue cuando un modelo tiene dos fichas: una
# persona es integrante o colabora desde fuera.
PIECES = {
    "content:article_detail": (Article, {}),
    "content:poem_detail": (Poem, {}),
    "content:section_detail": (Section, {}),
    "content:tag_detail": (Tag, {}),
    "content:collection_detail": (Collection, {}),
    "content:page_detail": (Page, {}),
    "content:contributor_detail": (Contributor, {"is_member": False}),
    "people:member_detail": (Contributor, {"is_member": True}),
    "media:recording_detail": (Recording, {}),
    "agenda:event_detail": (Event, {}),
    "showcase:publication_detail": (Publication, {}),
    "reviews:work_detail": (Work, {}),
    "reviews:publisher_detail": (Publisher, {}),
    "reviews:bookauthor_detail": (BookAuthor, {}),
}
ENTITY_ROUTES = {route for route, kind in ROUTES.items() if kind == ENTITY}


def test_every_entity_page_names_the_model_of_its_pieces():
    """Las fichas son las rutas de categoría «ficha» de test_completeness.py, que a su vez falla
    si una ruta del sitio no tiene categoría: una ficha nueva entra aquí con su modelo, y la prueba
    siguiente le exige su dirección."""
    assert set(PIECES) == ENTITY_ROUTES


@pytest.mark.parametrize("route", sorted(PIECES))
def test_every_model_with_a_public_page_knows_its_address(route):
    model, fields = PIECES[route]
    piece = model(slug="una-pieza", **fields)
    match = resolve(piece.get_absolute_url())
    assert (match.view_name, match.kwargs) == (route, {"slug": "una-pieza"})


def _work(name):
    """Una obra con su editorial y su autora, todas con el nombre dado."""
    publisher = Publisher.objects.create(slug=f"editorial-{name}", name=f"Editorial {name}")
    author = BookAuthor.objects.create(slug=f"autora-{name}", name=f"Autora {name}")
    work = Work.objects.create(slug=f"obra-{name}", title=f"Obra {name}", publisher=publisher)
    work.authors.add(author)
    return work


def _reviews():
    """Un texto publicado, en una sección y con una etiqueta, que reseña una obra: la obra, su
    editorial y su autora tienen ficha. Y otra obra que solo reseña un texto archivado: ni ella ni
    su editorial ni su autora la tienen."""
    section = Section.objects.create(slug="cronicas", name="Crónicas")
    tag = Tag.objects.create(slug="memoria", name="Memoria")
    article = make_published_article(section=section)
    article.tags.add(tag)
    reviewed = _work("vista")
    article.reviewed_works.add(reviewed)
    hidden = _work("oculta")
    make_article(status=EditorialStatus.ARCHIVED).reviewed_works.add(hidden)
    return {"section": section, "tag": tag, "reviewed": reviewed, "hidden": hidden}


def _of_work(work, kind):
    """La obra, su editorial o su autora."""
    return {"work": work, "publisher": work.publisher, "author": work.authors.get()}[kind]


@pytest.mark.parametrize("kind", ["work", "publisher", "author", "section", "tag"])
def test_the_address_of_a_work_and_of_what_classifies_a_text_leads_to_its_page(client, kind):
    world = _reviews()
    piece = world[kind] if kind in ("section", "tag") else _of_work(world["reviewed"], kind)
    response = client.get(piece.get_absolute_url())
    assert response.status_code == 200
    assert str(piece) in response.content.decode()


def _view_on_site(client, piece):
    """El botón «Ver en el sitio» de la ficha de la pieza en el panel, o None. Exige el de su
    historial, que va en la misma barra: es el control de que la barra se dibujó."""
    meta = piece._meta
    page = soup(
        client, reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[piece.pk])
    )
    assert page.find("a", string="Histórico"), "control: la ficha del panel dibuja su barra"
    return page.find("a", string="Ver en el sitio")


def _lands_on(client, button):
    """Adónde llega quien pulsa el botón, y con qué respuesta."""
    response = client.get(button["href"], follow=True)
    return response.request["PATH_INFO"], response.status_code


@pytest.mark.parametrize("kind", ["work", "publisher", "author"])
def test_the_panel_offers_view_on_site_only_where_the_public_page_exists(client, editor, kind):
    """Una obra, una editorial o una autora de obra tienen ficha mientras algo publicado las
    respalda. El botón lleva a la ficha que existe, y no está donde llevaría a un 404."""
    world = _reviews()
    with_page, without_page = (_of_work(world[w], kind) for w in ("reviewed", "hidden"))
    client.force_login(editor)

    button = _view_on_site(client, with_page)
    assert button is not None
    assert _lands_on(client, button) == (with_page.get_absolute_url(), 200)

    assert _view_on_site(client, without_page) is None
    assert client.get(without_page.get_absolute_url()).status_code == 404


def test_the_panel_offers_view_on_site_for_a_person_only_while_she_has_a_page(client, editor):
    """Una persona de fuera del colectivo tiene ficha mientras firma algo publicado; sin firmas
    publicadas, su ficha responde 404 y el panel no ofrece el botón."""
    signs = Contributor.objects.create(slug="firma-publicada", display_name="Firma Publicada")
    make_published_article().authors.add(signs)
    unsigned = Contributor.objects.create(slug="firma-en-borrador", display_name="Firma Borrador")
    make_article().authors.add(unsigned)
    client.force_login(editor)

    button = _view_on_site(client, signs)
    assert button is not None
    assert _lands_on(client, button) == (signs.get_absolute_url(), 200)

    assert _view_on_site(client, unsigned) is None
    assert client.get(unsigned.get_absolute_url()).status_code == 404


@pytest.mark.parametrize("kind", ["section", "tag"])
def test_the_panel_offers_view_on_site_for_every_section_and_tag(client, editor, kind):
    """Las secciones y las etiquetas tienen ficha siempre, también sin textos publicados."""
    piece = _reviews()[kind]
    empty = type(piece).objects.create(slug="sin-textos", name="Sin textos")
    client.force_login(editor)
    for shown in (piece, empty):
        button = _view_on_site(client, shown)
        assert button is not None
        assert _lands_on(client, button) == (shown.get_absolute_url(), 200)


TEMPLATES = Path(settings.BASE_DIR) / "templates"


def _literal(bit):
    """El texto de un argumento entre comillas, o None si es una variable."""
    quoted = len(bit) > 1 and bit[0] == bit[-1] and bit[0] in "'\""
    return bit[1:-1] if quoted else None


def _composed_addresses(source):
    """Los `{% url %}` de una plantilla que componen la dirección de una ficha. Las páginas
    legales se enlazan por su slug, que es fijo (LEGAL_PAGES): en esas plantillas no hay pieza."""
    found = []
    for token in Lexer(source).tokenize():
        bits = token.split_contents() if token.token_type == TokenType.BLOCK else []
        if bits[:1] != ["url"] or len(bits) < 2:
            continue
        route = _literal(bits[1])
        args = bits[2 : bits.index("as")] if "as" in bits else bits[2:]
        legal_page = (
            route == "content:page_detail" and len(args) == 1 and _literal(args[0]) in LEGAL_PAGES
        )
        if route in ENTITY_ROUTES and not legal_page:
            found.append(token.contents)
    return found


def test_no_template_composes_the_address_of_a_piece_by_its_route_name():
    """La dirección de una pieza sale de su `get_absolute_url`. Control: la comprobación reconoce
    una dirección compuesta, también la de una página que no es legal."""
    assert _composed_addresses("""<a href="{% url 'reviews:work_detail' w.slug %}">""") == [
        "url 'reviews:work_detail' w.slug"
    ]
    assert _composed_addresses("""{% url "content:page_detail" "bases" as bases %}""") == [
        'url "content:page_detail" "bases" as bases'
    ]
    assert _composed_addresses("""{% url 'content:page_detail' 'privacidad' %}""") == []
    templates = [path for path in TEMPLATES.rglob("*") if path.is_file()]
    assert len(templates) > 50, "control: se leen las plantillas"
    composed = {
        str(path.relative_to(TEMPLATES)): found
        for path in templates
        if (found := _composed_addresses(path.read_text(encoding="utf-8")))
    }
    assert composed == {}


# Las rutas públicas son permanentes: enlaces en prensa, dossiers, correos, buscadores y
# lectores de feeds dependen de ellas. Renombrar una exige dejar la vieja con
# RedirectView(permanent=True), que sigue resolviendo; borrarla de esta lista exige
# preguntarse antes quién la enlaza. Cada ruta va con un ejemplo concreto.
PUBLIC_PATHS = [
    "/",
    "/textos/",
    "/texto/un-texto/",
    "/buscar/",
    "/poemas/",
    "/poema/un-poema/",
    "/seccion/resenas/",
    "/etiqueta/memoria/",
    "/colaborador/una-firma/",
    "/colecciones/",
    "/coleccion/una-coleccion/",
    "/pagina/privacidad/",
    "/integrantes/",
    "/integrante/una-integrante/",
    "/registros/",
    "/registro/una-lectura/",
    "/archivo/registro/una-lectura/3f2a.mp3",
    "/agenda/",
    "/trayectoria/",
    "/galeria/",
    "/evento/un-recital/",
    "/dossier/",
    "/dossier.pdf",
    "/publicaciones/",
    "/publicacion/un-libro/",
    "/publicacion/un-libro.pdf",
    "/archivo/publicacion/un-libro/3f2a.pdf",
    "/prensa/",
    "/aliados/",
    "/novedades/",
    "/novedades/confirmar/un-token/",
    "/novedades/baja/un-token/",
    "/obra/una-obra/",
    "/editorial/una-editorial/",
    "/autor/un-autor/",
    "/enviar/",
    "/enviar/gracias/",
    "/feed/",
    "/feed/registros/",
    "/sitemap.xml",
    "/robots.txt",
    "/favicon.ico",
    "/healthz/",
    "/readyz/",
]
# Rutas que no circulan fuera del sitio: el panel y la descarga de adjuntos, que solo
# enlaza el panel. En desarrollo, además, los medios los sirve Django.
NOT_PUBLIC_PREFIXES = ("admin/", "envios/", "^media/")


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_path_still_resolves(path):
    resolve(path)  # Resolver404 si la ruta desapareció sin dejar su redirección


def _routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            yield route


def test_every_public_route_is_in_the_frozen_list():
    """Una ruta nueva entra en la lista: así queda fijada desde que existe."""
    frozen = {resolve(path).route for path in PUBLIC_PATHS}
    current = {
        route
        for route in _routes(get_resolver().url_patterns)
        if not route.startswith(NOT_PUBLIC_PREFIXES)
    }
    assert current == frozen
