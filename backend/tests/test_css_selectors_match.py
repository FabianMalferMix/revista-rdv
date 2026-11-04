"""Cada selector de las hojas casa en alguna página.

Cuando una plantilla cambia de estructura, las reglas que la estilaban dejan de aplicarse sin
dar error, y quien las lee después cree que siguen haciendo algo. Esta prueba pinta una página
de cada tipo, con datos que cubren sus estados opcionales, y exige que cada selector de cada hoja
case, con soupsieve, en alguna de las páginas que cargan esa hoja.

Antes de buscar, se quita del selector lo que no viene en el HTML del servidor:

- los pseudoelementos (`::before`, `::-webkit-details-marker`, las capas de una transición de
  vista…), que soupsieve no admite: cuelgan del elemento que nombra el resto del selector;
- los estados que da el navegador (`BROWSER_STATES`: `:hover`, `:focus-visible`, `:target`…)
  y el `[open]` del desplegable que abre la persona;
- las marcas que pone un guion (`SCRIPT_MARKS`), solo en el elemento donde la pone.

Un compuesto que se queda sin nada pasa a ser `*`: era un estado o un elemento que crea un
guion. Dentro de `:is()`, `:where()` y `:has()` se quita lo mismo; dentro de `:not()`, nada,
porque el HTML del servidor no trae esos estados ni esas marcas y la negación ya se cumple. El
contexto de la regla no cuenta: una regla de `@media print` o del teléfono también estila algo
que tiene que existir.
"""

import re
from datetime import timedelta

import pytest
import soupsieve as sv
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.template import loader
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Event, Milestone
from apps.community.models import NewsletterSubscriber
from apps.content.models import (
    Article,
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialNote,
    EditorialStatus,
    Section,
    Tag,
)
from apps.media.models import MediaAsset, Recording
from apps.people.models import Contributor, SocialLink
from apps.reviews.models import BookAuthor, Publisher, Work
from apps.showcase.models import Partner, PressMention, SiteProfile, SiteSocialLink, WhereToBuy
from apps.submissions.models import Call
from tests import css
from tests.factories import make_event, make_image, make_photo, make_publication, make_recording

STATIC = css.SITE_CSS.parent.parent
# Cada hoja, por cómo la nombran las páginas que la cargan.
SHEETS = {
    "css/site.css": css.site(),
    "admin/editorial_notes.css": css.Stylesheet(
        (STATIC / "admin" / "editorial_notes.css").read_text(encoding="utf-8")
    ),
}

# Lo que hace la persona en el navegador: señalar, enfocar, pulsar, haber visitado un enlace o
# llegar con un ancla en la dirección (`:target`: la foto ampliada de la galería).
BROWSER_STATES = frozenset(
    {"hover", "focus", "focus-visible", "focus-within", "active", "visited", "target"}
)
# Y el desplegable que abre (la lupa, «Menú», «Ver las N fotos», la transcripción).
BROWSER_ATTRIBUTES = frozenset({"open"})

# Las marcas que pone un guion y no el HTML del servidor: el elemento que la lleva (None: uno que
# crea el propio guion), la marca, el guion que la pone (en static/) y cuándo la pone.
SCRIPT_MARKS = (
    ("html", "[data-barra]", "js/cabecera.js", "en cuanto carga la página"),
    ("html", '[data-barra="arriba"]', "js/cabecera.js", "mientras se ve la cabecera entera"),
    ("html", '[data-barra="pildora"]', "js/cabecera.js", "al bajar, la cápsula"),
    (None, ".barra-centinela", "js/cabecera.js", "el centinela que mide si se bajó"),
    (".tirada", ".con-js", "js/registros.js", "al montarse la pila"),
    (".pliego", "[aria-current]", "js/registros.js", "en el pliego de arriba de la pila"),
    (".tirada-contacto", "[aria-current]", "js/registros.js", "en el contacto de ese pliego"),
    (".pliego", ".pliego--repartiendo", "js/registros.js", "mientras dura el reparto"),
    (".home-integrantes", ".con-js", "js/integrantes.js", "al montarse el relevo"),
    (".integrante", ".sr-only", "js/integrantes.js", "en las que esperan su turno"),
    (None, ".integrante--par", "js/integrantes.js", "en los lugares pares de la fila"),
    (None, ".integrante-tinta", "js/integrantes.js", "la pasada de tinta de un relevo"),
    (None, ".integrante-tinta--atras", "js/integrantes.js", "la pasada al deslizar atrás"),
    (None, "iframe", "js/embeds.js", "el reproductor, al pulsar «Reproducir»"),
    (None, ".htmx-request", "vendor/htmx/htmx.min.js", "mientras dura la búsqueda en vivo"),
)


# ── Lo que el selector le pide al HTML del servidor ─────────────────────────────


def _closing(text, start):
    """Dónde se cierra el paréntesis o el corchete que se abre en `start`."""
    pairs, expected, quote = {"(": ")", "[": "]"}, [], None
    for i in range(start, len(text)):
        char = text[i]
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in pairs:
            expected.append(pairs[char])
        elif char == expected[-1]:
            expected.pop()
            if not expected:
                return i
    raise AssertionError(f"selector sin cerrar: {text}")


def _split(text, separator):
    """Los tramos de `text` entre cada `separator` que no va dentro de paréntesis, corchetes ni
    comillas."""
    parts, current, depth, quote = [], "", 0, None
    for char in text:
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    return [part.strip() for part in (*parts, current) if part.strip()]


def _simple_selectors(compound):
    """Las piezas de un compuesto: `a`, `.clase`, `#id`, `[atributo]`, `:estado`, `:funcion(…)`
    y `::pseudoelemento`."""
    start = 0
    while start < len(compound):
        if compound[start] == "[":
            end = _closing(compound, start) + 1
        else:
            end = start + (2 if compound.startswith("::", start) else 1)
            while end < len(compound) and (compound[end].isalnum() or compound[end] in "-_"):
                end += 1
            if compound[end : end + 1] == "(":
                end = _closing(compound, end) + 1
        yield compound[start:end]
        start = end


def _server_compound(compound):
    pieces = list(_simple_selectors(compound))
    kept = []
    for piece in pieces:
        name, _, arguments = piece.lstrip(":").partition("(")
        if piece.startswith("::") or (piece.startswith(":") and name in BROWSER_STATES):
            continue
        if piece.startswith("[") and re.match(r"\[([\w-]+)", piece)[1] in BROWSER_ATTRIBUTES:
            continue
        if any(piece == mark and (on in (None, *pieces)) for on, mark, _, _ in SCRIPT_MARKS):
            continue
        if piece.startswith(":") and name in ("is", "where", "has"):
            piece = f":{name}({server_selector(arguments[:-1])})"
        kept.append(piece)
    return "".join(kept) or "*"


def server_selector(selector):
    """El selector (o la lista) sin lo que añaden el navegador y los guiones. Llega como lo
    escribe tests/css.py: un espacio a cada lado de cada combinador y tras cada coma."""
    return ", ".join(
        " ".join(
            part if part in (">", "+", "~") else _server_compound(part)
            for part in _split(complex_selector, " ")
        )
        for complex_selector in _split(selector, ",")
    )


def _classes_and_ids(selector):
    """Las clases y los id que nombra el selector fuera de `:is()`, `:has()` y `:not()`: una
    página que no los tiene todos no puede casar, y no hace falta recorrerla."""
    return {
        piece
        for compound in _split(selector, " ")
        for piece in _simple_selectors(compound)
        if piece[0] in ".#"
    }


def _unmatched(sheet, soups):
    """Los selectores de la hoja que no casan en ninguna de esas páginas, con dónde están."""
    pages = [
        (
            soup,
            {f".{name}" for tag in soup.select("[class]") for name in tag["class"]}
            | {f"#{tag['id']}" for tag in soup.select("[id]")},
        )
        for soup in soups
    ]
    missing = []
    for rule in sheet.rules:
        if any(at_rule.startswith("@keyframes") for at_rule in rule.context):
            continue  # `from`, `to` y los porcentajes no son selectores
        where = " › ".join(rule.context) or "fuera de toda at-rule"
        for selector in rule.selectors:
            server = server_selector(selector)
            try:
                pattern = sv.compile(server)
            except sv.SelectorSyntaxError as error:
                reason = str(error).splitlines()[0]
                missing.append(f"«{selector}» (línea {rule.line}, {where}): {reason}")
                continue
            needed = _classes_and_ids(server)
            if not any(needed <= names and pattern.select_one(soup) for soup, names in pages):
                missing.append(f"«{selector}» (línea {rule.line}, {where})")
    return missing


def _loading(sheet, pages):
    """Las páginas que cargan esa hoja."""
    return [
        soup
        for soup in pages
        if any(sheet in link.get("href", "") for link in soup.select("link[rel=stylesheet]"))
    ]


# ── Los datos ───────────────────────────────────────────────────────────────────

# Un título largo, que la ficha compone un paso más chico.
LONG_TITLE = (
    "Un título tan largo que la ficha de lectura lo compone un paso más chico, "
    "para que no ocupe media pantalla antes del primer verso"
)


def _image(name, caption="", credit=""):
    """Una imagen real, con el pie y el crédito que enseñan algunas fichas."""
    image = make_image(name, alt=name)
    image.caption, image.credit = caption, credit
    image.save()
    return image


def _audio(name):
    """El archivo subido de un registro: el panel solo admite audio."""
    return ContentFile(b"ID3" + b"\0" * 64, name=name)


def _people():
    """Siete integrantes, más de las que caben en la fila de la portada (el relevo), con todo lo
    que enseña una ficha; la primera, sin retrato (el monograma) y con sus redes. Una histórica
    y una firma invitada, que no es del colectivo."""
    members = [
        Contributor.objects.create(
            slug=f"voz-{n}",
            display_name=f"Voz {n}",
            is_member=True,
            position=n,
            role="Poeta",
            member_since=2023,
            short_bio="Escribe y lee en voz alta.",
            bio="Publicó dos libros.\n\nLee en ferias.",
            poetics="La poesía es repetir.",
            website="https://example.org/",
            photo=make_image(f"retrato-{n}", alt=f"Voz {n}") if n else None,
        )
        for n in range(7)
    ]
    SocialLink.objects.create(
        contributor=members[0], platform="Instagram", url="https://www.instagram.com/voz0/"
    )
    Contributor.objects.create(
        slug="historica", display_name="Histórica", is_member=True, active=False
    )
    guest = Contributor.objects.create(slug="invitada", display_name="Firma Invitada")
    return members, guest


def _profile(featured_poem):
    """El perfil del colectivo: lo que dicen la portada, el pie y el dossier."""
    profile = SiteProfile.load()
    profile.name = "Repitentes del Verso"
    profile.tagline = "Colectivo de poesía"
    profile.location = "Santiago"
    profile.founded_year = 2023
    profile.manifesto = "Un colectivo que lee en voz alta. Y escribe en compañía."
    profile.general_email = "hola@example.org"
    profile.booking_email = "gestion@example.org"
    profile.phone = "+56 9 1234 5678"
    profile.featured_poem = featured_poem
    profile.save()
    SiteSocialLink.objects.create(
        profile=profile, platform="Instagram", url="https://www.instagram.com/colectivo/"
    )


def _work(members, guest, make_article, make_poem):
    """Catorce textos y catorce poemas, para que los índices tengan dos páginas. Todos los textos
    llevan sección, etiqueta y un cuerpo con cita, código y figura. El primero de cada uno, con
    todo lo demás que puede llevar: título largo y colección; el texto, imagen con pie y obras
    reseñadas con y sin tapa; el poema, epígrafe."""
    section = Section.objects.create(slug="resenas", name="Reseñas", description="Lecturas.")
    tag = Tag.objects.create(slug="poesia-chilena", name="poesía chilena")
    publisher = Publisher.objects.create(
        slug="cuarto-propio", name="Cuarto Propio", country="Chile", website="https://example.org/"
    )
    author = BookAuthor.objects.create(slug="autora", name="Autora Reseñada", bio="Poeta.")
    reviewed = [
        Work.objects.create(
            slug="la-casa-vacia",
            title="La casa vacía",
            publisher=publisher,
            publication_year=2022,
            cover_image=make_image("cubierta-obra"),
            description="Poemas.",
        ),
        Work.objects.create(slug="sin-tapa", title="Sin tapa", publisher=publisher),
    ]
    for work in reviewed:
        work.authors.add(author)
    body = (
        "<p>Un párrafo con <a href='https://example.org/'>un enlace</a>.</p>"
        "<h2>Un subtítulo</h2><blockquote><p>Una cita.</p></blockquote>"
        "<pre><code>verso = repetir()</code></pre><ul><li>uno</li></ul>"
        "<figure><img src='/media/x.jpg' alt='x' width='30' height='40'>"
        "<figcaption>Un pie.</figcaption></figure>"
    )
    articles, poems = [], []
    for n in range(14):
        article = make_article(
            slug=f"texto-{n}",
            title=LONG_TITLE if n == 0 else f"Texto {n}",
            subtitle="Una bajada",
            excerpt="Un extracto.",
            body=body,
            section=section,
            status=EditorialStatus.PUBLISHED,
            # La portada enseña los tres últimos: el último, con su imagen.
            cover_image=_image(f"texto-{n}", "Un pie", "Foto: Ana") if n in (0, 13) else None,
        )
        article.authors.add(members[n % 3] if n else guest)
        article.tags.add(tag)
        articles.append(article)
        poem = make_poem(
            slug=f"poema-{n}",
            title=LONG_TITLE if n == 0 else f"Poema {n}",
            epigraph="A quien lee." if n == 0 else "",
            status=EditorialStatus.PUBLISHED,
        )
        poem.authors.add(members[n % 3] if n else guest)
        poems.append(poem)
    articles[0].authors.add(members[1])
    articles[0].reviewed_works.add(*reviewed)
    collection = Collection.objects.create(
        slug="antologia",
        title="Antología",
        description="Una selección.",
        intro="Lo que reúne.",
        cover_image=make_image("tapa-antologia"),
        status=EditorialStatus.PUBLISHED,
    )
    CollectionArticle.objects.create(collection=collection, article=articles[0])
    CollectionPoem.objects.create(collection=collection, poem=poems[0])
    return {
        "section": section,
        "tag": tag,
        "publisher": publisher,
        "author": author,
        "work": reviewed[0],
        "articles": articles,
        "poems": poems,
        "collection": collection,
    }


def _recordings(members, poems, event):
    """Los cinco registros destacados de la tirada: con póster, sin imagen, con la foto de su
    evento, de audio con su poema y de título largo. Fuera de ella, un video subido como archivo
    (con su poema), un audio con póster y un enlace que no se incrusta (que la búsqueda
    encuentra junto a las integrantes)."""
    con_poster = make_recording(
        slug="con-poster",
        title="Con póster",
        featured=True,
        position=0,
        poster=make_image("poster-registro"),
        event=event,
        duration_minutes=42,
        recorded_on=timezone.now().date(),
        transcript="Lo que se lee.",
        description="Una lectura.",
    )
    con_poster.participants.add(*members[:2])
    make_recording(slug="sin-imagen", title="Sin imagen", featured=True, position=1)
    make_recording(slug="con-foto", title="Con foto", featured=True, position=2, event=event)
    poems[1].recording = make_recording(
        slug="de-audio",
        title="De audio",
        featured=True,
        position=3,
        kind=Recording.Kind.AUDIO,
        embed_url="",
        file=_audio("lectura.mp3"),
    )
    poems[1].save()
    make_recording(
        slug="titulo-largo",
        title="Un registro con un título tan largo que ocupa dos líneas",
        featured=True,
        position=4,
    )
    poems[2].recording = make_recording(
        slug="video-subido", title="Video subido", embed_url="", file=_audio("lectura.mp3")
    )
    poems[2].save()
    make_recording(
        slug="audio-con-poster",
        title="Audio con póster",
        kind=Recording.Kind.AUDIO,
        embed_url="",
        file=_audio("audio.mp3"),
        poster=make_image("poster-audio"),
    )
    make_recording(slug="a-viva-voz", title="A viva voz", embed_url="https://example.org/")


def _agenda(members):
    """Una actividad anunciada, con afiche y todos sus datos, y otra de un tercero; y las ya
    hechas, con álbumes de una, dos, tres, cuatro, cinco y siete fotos (la última, con las que
    no caben en el mosaico). Y un hito de la trayectoria."""
    next_event = make_event(
        slug="proxima",
        title="Próxima lectura",
        poster=_image("afiche", "La sala llena", "Foto: Ana"),
        venue_name="La Sala",
        address="Calle 1",
        city="Santiago",
        description="Lectura abierta.",
        registration_url="https://example.org/entradas",
    )
    next_event.participants.add(members[0])
    make_event(
        slug="de-un-tercero",
        title="De un tercero",
        type=Event.Type.FESTIVAL,
        is_external=True,
        host="Feria del Libro",
        starts_at=timezone.now() + timedelta(days=20),
    )
    past = []
    for photos in (1, 2, 3, 4, 5, 7):
        event = make_event(
            slug=f"album-{photos}",
            title=f"Álbum de {photos}",
            starts_at=timezone.now() - timedelta(days=30 * photos),
            city="Valparaíso",
        )
        for position in range(photos):
            photo = make_photo(event, position)
            photo.caption = "Una lectura"
            photo.save()
            photo.asset.credit = "Foto: Ana"
            photo.asset.save()
        past.append(event)
    Milestone.objects.create(year=2024, title="Primer libro", description="Salió el primero.")
    return next_event, past


def _showcase(members):
    """El estante: una publicación de lomo oscuro, una de lomo claro y una sin tapa, de los tres
    tipos que tienen lomo propio. Prensa y aliados con logo y sin él, y una convocatoria abierta
    (el sello de la portada)."""
    dark, light = make_image("tapa-oscura"), make_image("tapa-clara")
    # El color del borde lo mide el servicio de imágenes después de la subida, fuera de la
    # petición: aquí se da el que mediría.
    MediaAsset.objects.filter(pk=dark.pk).update(border_color="#1f2a44")
    MediaAsset.objects.filter(pk=light.pk).update(border_color="#f6d6e6")
    publications = [
        make_publication(
            slug="de-frente",
            title="De frente",
            cover=dark,
            featured=True,
            publisher=Publisher.objects.create(slug="propia", name="Ediciones del Verso"),
            synopsis="Poemas reunidos.",
            is_own=True,
            pdf=ContentFile(b"%PDF-1.4", name="libro.pdf"),
        ),
        make_publication(slug="tapa-clara", title="Tapa clara", cover=light, kind="libro"),
        make_publication(slug="sin-tapa", title="Sin tapa", year=None, kind="fanzine"),
    ]
    publications[0].participants.add(*members[:2])
    WhereToBuy.objects.create(
        publication=publications[0], label="Librería", url="https://example.org/"
    )
    PressMention.objects.create(
        title="Entrevista",
        outlet="Radio",
        author="Periodista",
        kind=PressMention.Kind.ENTREVISTA,
        published_on=timezone.now().date(),
        url="https://example.org/",
        quote="Un colectivo que lee.",
        logo=make_image("logo-medio"),
    )
    PressMention.objects.create(title="Mención", outlet="Diario")
    Partner.objects.create(
        name="Fondo",
        kind=Partner.Kind.FINANCIAMIENTO,
        logo=make_image("logo-fondo"),
        url="https://example.org/",
        description="Financia.",
    )
    Partner.objects.create(name="Espacio sin logo", kind=Partner.Kind.ESPACIO)
    Call.objects.create(
        slug="convocatoria",
        title="Convocatoria",
        opens_at=timezone.now() - timedelta(days=1),
        closes_at=timezone.now() + timedelta(days=30),
    )
    return publications


def _with_search_results(page, panel):
    """La página con la lupa abierta y sus resultados: htmx mete la respuesta del servidor en
    #search-results (`hx-target`, con el intercambio por defecto, `innerHTML`)."""
    soup = BeautifulSoup(page, "html.parser")
    soup.select_one("#search-results").append(BeautifulSoup(panel, "html.parser"))
    return soup


@pytest.fixture
def site_pages(client, groups, editor, make_article, make_poem, legal_pages):
    """Una página de cada tipo, y algunas más en otro estado: la portada y la agenda vuelven a
    pedirse después de cambiar los datos que las deciden."""
    members, guest = _people()
    work = _work(members, guest, make_article, make_poem)
    _profile(featured_poem=work["poems"][3])
    next_event, past = _agenda(members)
    _recordings(members, work["poems"], event=past[1])
    publications = _showcase(members)
    subscriber = NewsletterSubscriber.objects.create(
        email="ana@example.org",
        token="tok-baja",
        confirm_token="tok-confirma",
        confirm_token_at=timezone.now(),
    )
    pages = []

    def keep(response, status=200):
        assert response.status_code == status, response.request["PATH_INFO"]
        pages.append(BeautifulSoup(response.content.decode(), "html.parser"))

    for url in (
        reverse("content:home"),
        reverse("content:text_archive"),
        reverse("content:text_archive") + "?page=2",
        reverse("content:poem_index"),
        *(piece.get_absolute_url() for piece in (*work["articles"][:2], *work["poems"][:3])),
        reverse("content:section_detail", args=[work["section"].slug]),
        reverse("content:tag_detail", args=[work["tag"].slug]),
        reverse("content:contributor_detail", args=[guest.slug]),
        reverse("content:collection_index"),
        work["collection"].get_absolute_url(),
        reverse("content:page_detail", args=["privacidad"]),
        reverse("content:search") + "?q=voz",
        reverse("content:search") + "?q=nadaquecoincida",
        reverse("people:member_index"),
        *(reverse("people:member_detail", args=[slug]) for slug in ("voz-0", "voz-1", "historica")),
        reverse("media:recording_index"),
        *(recording.get_absolute_url() for recording in Recording.objects.all()),
        reverse("agenda:agenda"),
        reverse("agenda:trayectoria"),
        reverse("agenda:gallery"),
        *(event.get_absolute_url() for event in (next_event, *past)),
        reverse("showcase:dossier"),
        reverse("showcase:publication_index"),
        *(publication.get_absolute_url() for publication in publications),
        reverse("showcase:press_index"),
        reverse("showcase:partner_index"),
        reverse("reviews:work_detail", args=[work["work"].slug]),
        reverse("reviews:publisher_detail", args=[work["publisher"].slug]),
        reverse("reviews:bookauthor_detail", args=[work["author"].slug]),
        reverse("submissions:submit"),
        reverse("submissions:submit_thanks"),
        reverse("community:confirm", args=[subscriber.confirm_token]),
        reverse("community:unsubscribe", args=[subscriber.token]),
    ):
        keep(client.get(url))
    keep(client.get("/no-existe/"), status=404)
    pages.append(BeautifulSoup(loader.render_to_string("500.html"), "html.parser"))

    # Lo que responde un envío: el formulario con errores, la confirmación y la baja del
    # boletín, y el aviso de un correo que no sirve, en la portada a la que se vuelve.
    keep(client.post(reverse("submissions:submit"), {"author_email": "no-es-un-correo"}))
    keep(client.post(reverse("community:confirm", args=[subscriber.confirm_token])))
    keep(client.post(reverse("community:unsubscribe", args=[subscriber.token])))
    keep(client.post(reverse("community:subscribe"), {"email": "ana@correo"}, follow=True))

    # La lupa con los resultados que pide htmx.
    panel = client.get(reverse("content:search") + "?q=voz", HTTP_HX_REQUEST="true")
    home = client.get(reverse("content:home")).content.decode()
    pages.append(_with_search_results(home, panel.content.decode()))

    # Lo que ve el equipo: la vista previa de un borrador y, en el panel, un texto con la nota
    # de otra persona, que se lee y no se escribe.
    draft = make_article(slug="borrador", title="Borrador", owner=editor)
    other = get_user_model().objects.create_user("editora_dos", password="pw", is_staff=True)
    other.groups.add(groups["editor"])
    EditorialNote.objects.create(
        content_type=ContentType.objects.get_for_model(Article),
        object_id=work["articles"][0].pk,
        author=other,
        body="Falta la fecha del recital.",
    )
    client.force_login(editor)
    keep(client.get(draft.get_absolute_url()))
    keep(client.get(reverse("admin:content_article_change", args=[work["articles"][0].pk])))
    client.logout()

    # Sin registros destacados, la portada enseña el poema destacado; sin integrantes, la obra
    # y el estante quedan seguidos; sin nada anunciado, la agenda enseña lo más reciente.
    Recording.objects.update(featured=False)
    Contributor.objects.update(active=False)
    Event.objects.filter(starts_at__gte=timezone.now()).update(published=False)
    keep(client.get(reverse("content:home")))
    keep(client.get(reverse("agenda:agenda")))
    return pages


# ── Las pruebas ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_every_selector_of_the_stylesheets_matches_some_page(site_pages):
    missing = []
    for sheet, parsed in SHEETS.items():
        pages = _loading(sheet, site_pages)
        assert pages, f"ninguna página carga {sheet}"
        missing += [f"{sheet}: {selector}" for selector in _unmatched(parsed, pages)]
    assert not missing, (
        "Estos selectores no casan en ninguna página: o la regla está muerta, o faltan datos "
        "para el estado que estila (en site_pages), o depende de algo que pone un guion "
        "(SCRIPT_MARKS) o el navegador (BROWSER_STATES).\n" + "\n".join(missing)
    )
    # Control: un selector que nombra algo que ninguna plantilla pinta sí se informa, aunque
    # lleve marcas de guion y estados del navegador.
    ghost = css.Stylesheet(".tirada.con-js .pliego[aria-current] .pliego-sin-plantilla:hover{}")
    assert _unmatched(ghost, _loading("css/site.css", site_pages)) == [
        "«.tirada.con-js .pliego[aria-current] .pliego-sin-plantilla:hover» "
        "(línea 1, fuera de toda at-rule)"
    ]


@pytest.mark.parametrize(
    "selector, server",
    [
        (".fila:has(.fila-titulo a):hover::before", ".fila:has(.fila-titulo a)"),
        (".player-consent :focus-visible", ".player-consent *"),
        (
            ".masthead-fila:has(.busqueda[open]) .busqueda",
            ".masthead-fila:has(.busqueda) .busqueda",
        ),
        (".tirada.con-js .pliego[aria-current] + .pliego", ".tirada .pliego + .pliego"),
        (".tirada.con-js .pliego:has(~ .pliego[aria-current])", ".tirada .pliego:has(~ .pliego)"),
    ],
)
def test_what_the_browser_and_the_scripts_add_is_left_out(selector, server):
    assert server_selector(selector) == server


@pytest.mark.parametrize(
    "selector",
    [
        # El aria-current de la barra lo pone el servidor; el de los pliegos, el guion.
        ".nav a[aria-current]",
        # Una negación ya se cumple en el HTML del servidor, que no trae ni estados ni marcas.
        ".search:not(:focus-within):not(:hover) #search-results",
        ".home-integrantes:not(.con-js) .integrantes-retratos > li:nth-child(2n)",
    ],
)
def test_what_the_server_sends_stays(selector):
    assert server_selector(selector) == selector


def test_each_script_mark_is_set_by_its_script_and_used_by_a_stylesheet():
    """Que la lista no se quede con marcas que ya nadie pone o que ya no usa ninguna hoja: una
    marca de más deja pasar una regla muerta."""
    selectors = [s for sheet in SHEETS.values() for rule in sheet.rules for s in rule.selectors]
    stale = []
    for on, mark, script, _ in SCRIPT_MARKS:
        source = (STATIC / script).read_text(encoding="utf-8")
        if not all(word in source for word in re.findall(r"[\w-]+", mark)):
            stale.append(f"{script} no pone {mark}")
        if not any(mark in s and (on is None or on in s) for s in selectors):
            stale.append(f"ninguna hoja usa {mark}" + (f" en {on}" if on else ""))
    assert not stale, stale
