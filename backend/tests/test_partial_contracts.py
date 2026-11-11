"""Las parciales con contrato: cada una dice en su cabecera qué recibe, en un bloque «Parámetros»
que marca lo obligatorio, y se incluye con `only`, con todo lo obligatorio y nada que no declare.

Sin `only`, una parcial hereda el contexto entero de la página que la incluye: una variable de la
vista con el nombre de uno de sus parámetros opcionales (una `cejilla`) se pinta donde nadie la
pidió. Lo que hoy da un procesador de contexto (`site_profile`, las redes, la sub-fila, el mapa)
también se le pasa por su nombre. Aquí se lee el bloque de cada parcial y se comprueba
con el motor de Django cada `{% include %}` del sitio, también los que van dentro de bloques,
bucles y condiciones. Y cada parcial se pinta con lo que declara y nada más: la suite usa
`string_if_invalid`, así que una variable que la parcial lee sin declararla hace fallar la prueba.
Las que pinta una etiqueta de inclusión se pintan con lo que devuelve su etiqueta, que también
tiene que ser lo que declaran.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.paginator import Paginator
from django.template import TemplateSyntaxError, engines
from django.template.loader import get_template
from django.template.loader_tags import IncludeNode

from apps.community.templatetags.newsletter import newsletter_form
from apps.content.models import Article, ArticleContributor, Poem, PoemContributor, Section
from apps.media.templatetags.images import responsive_img
from apps.media.templatetags.social import social_meta
from apps.people.models import Contributor
from apps.people.templatetags.personas import portrait
from apps.reviews.models import Publisher, Work
from apps.showcase.models import SiteProfile
from apps.showcase.templatetags.publications import cover
from apps.site import portada
from apps.site.navigation import site_map, subnav
from apps.site.templatetags.pie import cierre_pie
from apps.site.templatetags.portada import portada_img
from tests.factories import (
    make_event,
    make_image,
    make_photo,
    make_publication,
    make_published_article,
    make_published_poem,
    make_recording,
)

# Las que más páginas pintan: las tarjetas de texto y de poema, la cabecera de los índices y el
# pie de las fichas.
FIRST = {
    "partials/_article_card.html",
    "partials/_poem_card.html",
    "partials/_index_head.html",
    "partials/_pie_de_entidad.html",
}

# La línea que abre el bloque: «Parámetros», quizá una aclaración entre paréntesis, y dos puntos.
# Tras ellos, en la misma línea, puede decir que no recibe nada («ninguno»).
HEAD = re.compile(r"\s*Parámetros\b[^:]*:")


def _template_names():
    for folder in map(Path, settings.TEMPLATES[0]["DIRS"]):
        for path in sorted(folder.rglob("*.html")):
            yield folder, path.relative_to(folder).as_posix()


def _partials():
    """(carpeta, nombre) de cada parcial del sitio: las plantillas cuyo nombre empieza por «_»."""
    return [(folder, name) for folder, name in _template_names() if Path(name).name[0] == "_"]


def contract(source):
    """{parámetro: obligatorio} del bloque «Parámetros» del primer comentario de la parcial, o
    None si no lo tiene. Debajo de su línea va una entrada por parámetro: sus nombres a cinco
    espacios (varios, separados por comas, si van juntos), y lo que es, que puede seguir en las
    líneas siguientes, más sangradas. Es obligatorio el que lo dice: «(obligatorio)»."""
    start, end = source.find("{% comment %}"), source.find("{% endcomment %}")
    if start < 0 or end < start:
        return None
    lines = source[start:end].splitlines()
    heads = [i for i, line in enumerate(lines) if HEAD.match(line)]
    if not heads:
        return None
    entries = []
    for line in lines[heads[0] + 1 :]:
        names, _, rest = line[5:].partition("  ")
        if line.startswith("     ") and not line.startswith("      ") and rest.strip():
            entries.append(([name.strip() for name in names.split(",")], rest.strip()))
        elif line.startswith("      ") and entries:
            entries[-1] = (entries[-1][0], f"{entries[-1][1]} {line.strip()}")
        else:
            break
    return {name: "(obligatorio)" in text for names, text in entries for name in names}


def _contracts():
    found = {}
    for folder, name in _partials():
        declared = contract((folder / name).read_text(encoding="utf-8"))
        if declared is not None:
            found[name] = declared
    return found


def _includes():
    """(plantilla, nodo) por cada `{% include %}` con nombre fijo de las plantillas del sitio."""
    engine = engines["django"].engine
    for _, name in _template_names():
        for node in engine.get_template(name).nodelist.get_nodes_by_type(IncludeNode):
            if isinstance(node.template.var, str):
                yield name, node


def test_every_partial_declares_its_contract():
    partials = {name for _, name in _partials()}
    # Control: la búsqueda encuentra las parciales de la raíz, de `partials/` y de las apps.
    assert {"partials/_mapa.html", "site/partials/_tirada.html"} <= partials
    missing = sorted(partials - set(_contracts()))
    assert not missing, f"parciales sin su bloque «Parámetros»: {missing}"


def test_every_include_of_a_partial_passes_its_contract():
    contracts = _contracts()
    # Control: el bloque se lee, con lo obligatorio y lo opcional, en las cuatro primeras.
    assert FIRST <= set(contracts), f"sin contrato: {FIRST - set(contracts)}"
    card = contracts["partials/_article_card.html"]
    assert card["a"] is True and card["nivel"] is False
    problems, seen = [], set()
    for template, node in _includes():
        partial = node.template.var
        if partial not in contracts:
            problems.append(f"{template} incluye {partial}, que no declara qué recibe")
            continue
        seen.add((template, partial))
        declared, given = contracts[partial], set(node.extra_context)
        if not node.isolated_context:
            problems.append(f"{template} incluye {partial} sin `only`")
        if missing := sorted(p for p, required in declared.items() if required and p not in given):
            problems.append(f"{template} incluye {partial} sin {missing}, que es obligatorio")
        if extra := sorted(given - set(declared)):
            problems.append(f"{template} pasa a {partial} {extra}, que no declara")
    # Control: se leen las inclusiones de verdad, dentro de un bloque, de un bucle y de una
    # condición, y también las de una parcial dentro de otra.
    assert {
        ("content/text_archive.html", "partials/_index_head.html"),
        ("partials/_article_list.html", "partials/_article_card.html"),
        ("content/collection_detail.html", "partials/_poem_card.html"),
        ("site/home.html", "partials/_article_list.html"),
        ("base.html", "partials/_mapa.html"),
        ("media/partials/_player.html", "media/partials/_caratula.html"),
    } <= seen
    assert not problems, "\n".join(problems)


@pytest.fixture
def pieces():
    """Una pieza de cada cosa que pintan las parciales, con todo lo que enseñan."""
    member = Contributor.objects.create(
        slug="integrante",
        display_name="Integrante",
        is_member=True,
        photo=make_image("retrato"),
        role="Poeta",
        short_bio="Escribe y lee.",
    )
    other = Contributor.objects.create(slug="otra-firma", display_name="Otra firma")
    section = Section.objects.create(slug="cronica", name="Crónica")
    event = make_event(slug="recital", poster=make_image("afiche"))
    for n in range(2):
        article = make_published_article(
            slug=f"texto-{n}", subtitle="Bajada", section=section, cover_image=make_image(f"t{n}")
        )
        ArticleContributor.objects.create(article=article, contributor=member)
        ArticleContributor.objects.create(article=article, contributor=other, position=1)
        recording = make_recording(
            featured=True, position=n, poster=make_image(f"placa-{n}"), event=event
        )
        poem = make_published_poem(slug=f"poema-{n}", recording=recording)
        PoemContributor.objects.create(poem=poem, contributor=member)
    article = Article.objects.published().for_row().first()
    return {
        "member": member,
        "article": article,
        "poem": Poem.objects.published().for_row().first(),
        "articles": Paginator(Article.objects.published().for_row(), 1).get_page(1),
        "poems": Paginator(Poem.objects.published().for_row(), 1).get_page(1),
        "work": Work.objects.create(slug="obra", title="Obra", publication_year=2024),
        "photo": make_photo(event),
        "event": event,
        # Sin póster: la placa del reproductor lleva la carátula.
        "recording": make_recording(event=event),
        "publication": make_publication(
            slug="libro",
            cover=make_image("tapa"),
            publisher=Publisher.objects.create(slug="editorial", name="Editorial"),
        ),
        "profile": SiteProfile.load(),
        "tirada": portada.build_tirada(SiteProfile.load()),
    }


# Con qué pintar cada parcial: un valor por cada parámetro que declara. Las que pinta una etiqueta
# de inclusión, con lo que devuelve la etiqueta.
SAMPLES = {
    "partials/_article_card.html": lambda x: {
        "a": x["article"],
        "nivel": 3,
        "sin_firma_de": x["member"],
    },
    "partials/_poem_card.html": lambda x: {
        "p": x["poem"],
        "nivel": 3,
        "sin_cejilla": True,
        "versos": 3,
        "sin_firma_de": x["member"],
    },
    "partials/_article_list.html": lambda x: {
        "articles": x["articles"],
        "pagina": x["articles"],
        "nivel": 3,
        "sin_firma_de": x["member"],
    },
    "content/partials/_poem_list.html": lambda x: {"poems": x["poems"], "pagina": x["poems"]},
    "partials/_pagination.html": lambda x: {"pagina": x["articles"], "unidad": "textos"},
    "partials/_index_head.html": lambda x: {
        "titulo": "Integrantes",
        "subnav": subnav("people:member_index"),
        "cuenta": 2,
        "singular": "integrante",
        "plural": "integrantes",
        "cejilla": "El colectivo",
        "dek": "Quiénes son.",
        "territorio": "colectivo",
    },
    "partials/_pie_de_entidad.html": lambda x: cierre_pie("hola@example.com", "Para programar"),
    "reviews/partials/_work_list.html": lambda x: {"works": [x["work"]]},
    "site/partials/_cabeza_de_seccion.html": lambda x: {
        "titulo": "Las voces",
        "cejilla": "El colectivo",
        "territorio": "colectivo",
    },
    "agenda/partials/_foto.html": lambda x: {
        "foto": x["photo"],
        "numero": 1,
        "total": 1,
        "slug": x["event"].slug,
    },
    "agenda/partials/_event_card.html": lambda x: {"e": x["event"]},
    "content/partials/_firmas_lectura.html": lambda x: {"personas": x["article"].bylines},
    "media/partials/_caratula.html": lambda x: {"r": x["recording"]},
    "media/partials/_player.html": lambda x: {"r": x["recording"], "titulo_id": "registro"},
    "partials/_mapa.html": lambda x: {
        "mapa": site_map(),
        "en_menu": True,
        "site_profile": x["profile"],
        "redes_del_colectivo": [{"platform": "Instagram", "url": "https://instagram.com/rdv"}],
        "etiqueta": "Menú del sitio",
        "sin_contacto": True,
    },
    "partials/_newsletter_form.html": lambda x: newsletter_form({"csrf_token": "ficha"}),
    "partials/_publication_card.html": lambda x: {"pub": x["publication"]},
    "partials/_responsive_img.html": lambda x: responsive_img(
        x["member"].photo, sizes="96px", css_class="retrato"
    ),
    "partials/_sello.html": lambda x: {"site_name": x["profile"].name},
    "partials/_participan.html": lambda x: {
        "personas": Contributor.objects.with_page().filter(pk=x["member"].pk)
    },
    "partials/_cejilla_de_texto.html": lambda x: {"a": x["article"]},
    "partials/_tapa.html": lambda x: cover(x["publication"], "240px", css_class="ficha-cubierta"),
    "partials/_retrato.html": lambda x: portrait(x["member"], "96px", duotone=True),
    "partials/_social_meta.html": lambda x: social_meta({}, x["article"]),
    "people/partials/_member_card.html": lambda x: {"m": x["member"]},
    "site/partials/_logo_apilado.html": lambda x: {},
    "site/partials/_logo_horizontal.html": lambda x: {},
    "site/partials/_member_card_portada.html": lambda x: {
        "m": x["member"],
        "escondida": True,
        "solo_ancho": True,
    },
    "site/partials/_portada_img.html": lambda x: portada_img(),
    "site/partials/_search_results.html": lambda x: {
        "q": "casa",
        "grupos": [
            {
                "titulo": "Textos",
                "resultados": [{"url": "/texto/casa/", "title": "Casa", "kind": "Reseña"}],
            }
        ],
        "total": 1,
        "aviso": "",
        "panel": True,
    },
    "site/partials/_tirada.html": lambda x: {"tirada": x["tirada"]},
}


def test_every_partial_with_a_contract_has_a_sample_here():
    assert set(SAMPLES) == set(_contracts())


@pytest.mark.django_db
@pytest.mark.parametrize("partial", sorted(SAMPLES))
def test_each_partial_renders_with_only_what_it_declares(partial, pieces):
    declared = _contracts()[partial]
    values = SAMPLES[partial](pieces)
    assert set(values) == set(declared), "un valor por cada parámetro que declara, y nada más"
    template = get_template(partial)
    # Una copia cada vez: lo que la parcial guarda con `as` va a parar al diccionario que recibe.
    assert template.render(dict(values)).strip()
    # Lo opcional lo es: con solo lo obligatorio también se pinta.
    required = {name: value for name, value in values.items() if declared[name]}
    assert template.render(required).strip()


@pytest.mark.django_db
def test_the_pagination_fails_with_a_list_that_is_not_a_page(pieces):
    """Una consulta en lugar de una página dejaría la lista sin tope y sin paginación, y sin
    ningún aviso: la suite falla. Sin página (None) no se pinta nada."""
    template = get_template("partials/_pagination.html")
    assert "1–1 de 2 textos" in " ".join(
        template.render({"pagina": pieces["articles"], "unidad": "textos"}).split()
    )
    assert template.render({"pagina": None}).strip() == ""
    with pytest.raises(TemplateSyntaxError):
        template.render({"pagina": Article.objects.published()})
