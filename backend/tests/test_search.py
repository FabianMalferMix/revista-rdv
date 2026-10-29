"""Vista de búsqueda FTS en vivo (htmx): artículos y poemas — Lotes F2-6 / F3-1."""

import re

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.content.models import Article, EditorialStatus, Poem
from tests.factories import publish as _publish

pytestmark = pytest.mark.django_db
S = EditorialStatus


def test_search_finds_published_match(client, make_article):
    _publish(make_article(slug="fts-1", title="Reseña de poesía chilena"))
    resp = client.get(reverse("content:search"), {"q": "poesía"})
    assert resp.status_code == 200
    assert "Reseña de poesía chilena".encode() in resp.content
    assert b"search-list" in resp.content


def test_search_excludes_drafts(client, make_article):
    make_article(slug="fts-draft", title="Borrador secreto de poesía", status=EditorialStatus.DRAFT)
    resp = client.get(reverse("content:search"), {"q": "secreto"})
    assert b"Borrador secreto" not in resp.content
    assert b"Sin resultados" in resp.content


def test_search_empty_query_renders_nothing(client, make_article):
    _publish(make_article(slug="fts-2", title="Algo publicado"))
    resp = client.get(reverse("content:search"), {"q": ""})
    assert resp.status_code == 200
    assert b"Algo publicado" not in resp.content
    assert b"search-list" not in resp.content  # ni lista ni estado vacío


def test_search_no_match_shows_empty_state(client, make_article):
    _publish(make_article(slug="fts-3", title="Reseña de narrativa urbana"))
    resp = client.get(reverse("content:search"), {"q": "zxqwvk"})
    assert b"Sin resultados" in resp.content
    assert b"search-list" not in resp.content


def test_search_finds_published_poem(client, make_poem):
    _publish(make_poem(slug="poema-fts", title="Elegía del faro", body="luz que gira en la niebla"))
    resp = client.get(reverse("content:search"), {"q": "faro"})
    assert resp.status_code == 200
    assert "Elegía del faro".encode() in resp.content
    assert b"Poema" in resp.content  # kicker de tipo
    assert reverse("content:poem_detail", args=["poema-fts"]).encode() in resp.content


def test_search_excludes_draft_poems(client, make_poem):
    make_poem(slug="poema-draft", title="Poema oculto del abismo", body="secretos", status=S.DRAFT)
    resp = client.get(reverse("content:search"), {"q": "abismo"})
    assert b"Poema oculto" not in resp.content
    assert b"Sin resultados" in resp.content


def test_poem_search_vector_tracks_bulk_update(client, make_poem):
    # QuerySet.update NO pasa por save(): con el trigger, el vector igual se refresca
    # (el enfoque previo, que recalculaba solo en save(), dejaba el vector obsoleto).
    poem = _publish(make_poem(slug="poema-bulk", title="Título inicial", body="palabra vieja"))
    Poem.objects.filter(pk=poem.pk).update(body="hipogrifo violento")
    resp = client.get(reverse("content:search"), {"q": "hipogrifo"})
    assert "Título inicial".encode() in resp.content


def test_article_search_vector_tracks_bulk_update(client, make_article):
    art = _publish(make_article(slug="art-bulk", title="Reseña bulk", body="palabra vieja"))
    Article.objects.filter(pk=art.pk).update(body="quetzalcoatl emplumado")
    resp = client.get(reverse("content:search"), {"q": "quetzalcoatl"})
    assert b"Rese\xc3\xb1a bulk" in resp.content


# ── Búsqueda insensible a acentos (unaccent) ────────────────────────────────


def test_search_unaccented_query_finds_accented_title(client, make_article):
    """Buscar 'resena' (sin acento) encuentra 'reseña' (con acento)."""
    _publish(make_article(slug="acentuado", title="La reseña de una novela chilena"))
    resp = client.get(reverse("content:search"), {"q": "resena"})
    assert "La reseña de una novela chilena".encode() in resp.content


def test_search_accented_query_finds_unaccented_title(client, make_article):
    """Buscar 'crónica' (con acento) encuentra 'cronica' (sin acento en la BD)."""
    _publish(make_article(slug="sin-acento", title="Cronica urbana del invierno"))
    resp = client.get(reverse("content:search"), {"q": "crónica"})
    assert b"Cronica urbana del invierno" in resp.content


# ── Degradación sin JavaScript (hallazgo #09) ───────────────────────────────


def test_search_without_js_returns_full_page(client, make_article):
    """Una navegación normal (sin htmx) recibe la página completa con layout, no un
    fragmento suelto: la búsqueda funciona sin JavaScript."""
    _publish(make_article(slug="fts-page", title="Reseña navegable"))
    html = client.get(reverse("content:search"), {"q": "navegable"}).content.decode()
    assert "<h1>Búsqueda</h1>" in html  # cabecera de la página completa
    assert "</html>" in html  # layout de base presente
    assert "Reseña navegable" in html  # el resultado aparece


def test_search_with_htmx_returns_fragment_only(client, make_article):
    """Con htmx (HX-Request) se devuelve solo el fragmento, sin el layout."""
    _publish(make_article(slug="fts-frag", title="Reseña fragmento"))
    resp = client.get(reverse("content:search"), {"q": "fragmento"}, headers={"HX-Request": "true"})
    html = resp.content.decode()
    assert "Reseña fragmento" in html
    assert "<h1>Búsqueda</h1>" not in html  # sin cabecera de página
    assert "</html>" not in html  # sin layout


# ── Panel en vivo y página de búsqueda (backlog UX, ticket 1.5) ─────────────


def test_el_panel_en_vivo_ofrece_una_salida_a_la_pagina(client, make_article):
    """El panel flotante es efímero; el enlace lleva a una página con URL estable.

    Va FUERA de la lista: otra prueba cuenta los <li> de `.search-list` para acotar el
    número de resultados, y un enlace dentro lo falsearía.
    """
    _publish(make_article(slug="fts-salida", title="Reseña con salida"))
    url = reverse("content:search")
    html = client.get(url, {"q": "salida"}, headers={"HX-Request": "true"}).content.decode()
    assert 'class="search-all"' in html
    assert f'href="{url}?q=salida"' in html
    lista = html[html.index('<ul class="search-list">') : html.index("</ul>")]
    assert "search-all" not in lista


def test_la_pagina_de_busqueda_no_repite_el_enlace_a_si_misma(client, make_article):
    _publish(make_article(slug="fts-misma", title="Reseña en página"))
    html = client.get(reverse("content:search"), {"q": "página"}).content.decode()
    assert "search-all" not in html


def test_la_pagina_de_busqueda_tiene_un_solo_campo(client):
    """Tenía dos a la vista: el de la cabecera con su panel y el de la página."""
    html = client.get(reverse("content:search")).content.decode()
    assert len(re.findall(r'<input[^>]*name="q"', html)) == 1
    assert 'id="search-results"' not in html


# ── Cobertura completa y grupos por tipo (backlog UX, ticket 5.4) ───────────

BUSCAR = reverse("content:search")


def _grupos(client, q, panel=False):
    """{cejilla: [(título, dato), …]} de los resultados, en su orden."""
    from bs4 import BeautifulSoup

    cabeceras = {"HX-Request": "true"} if panel else {}
    sopa = BeautifulSoup(client.get(BUSCAR, {"q": q}, headers=cabeceras).content, "html.parser")
    grupos = {}
    for grupo in sopa.select(".search-grupo"):
        filas = []
        for li in grupo.select(".search-list > li"):
            dato = li.select_one(".meta")
            filas.append((li.a.get_text(), dato.get_text() if dato else ""))
        grupos[grupo.h2.get_text()] = filas
    return grupos


def _integrante(nombre, slug, **extra):
    from apps.people.models import Contributor

    return Contributor.objects.create(display_name=nombre, slug=slug, is_member=True, **extra)


def test_fernanda_devuelve_a_la_integrante(client):
    """La aceptación del ticket: buscar un nombre lleva a la ficha de la integrante."""
    _integrante("Fernanda Soto", "fernanda-soto", role="Fundadora · edición")
    grupos = _grupos(client, "Fernanda")
    assert grupos == {"Personas": [("Fernanda Soto", "Fundadora · edición")]}
    html = client.get(BUSCAR, {"q": "Fernanda"}).content.decode()
    assert f'href="{reverse("people:member_detail", args=["fernanda-soto"])}"' in html


def test_recital_devuelve_el_registro_y_la_actividad(client):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from tests.factories import make_event, make_recording

    make_recording(slug="recital-registro", title="Recital «Nuevas voces» (registro)", kind="video")
    make_event(
        slug="recital-actividad",
        title="Recital de invierno",
        type="recital",
        city="Santiago",
        # A las 22:30 de Santiago, en UTC ya es el 11: la fecha es la de la hora local.
        starts_at=datetime(2026, 9, 10, 22, 30, tzinfo=ZoneInfo("America/Santiago")),
    )
    grupos = _grupos(client, "recital")
    assert list(grupos) == ["Registros", "Actividades"]
    assert grupos["Registros"] == [("Recital «Nuevas voces» (registro)", "Video")]
    assert grupos["Actividades"] == [("Recital de invierno", "Recital · 10 Sep 2026 · Santiago")]


def test_los_nombres_se_buscan_sin_acentos_ni_mayusculas(client):
    _integrante("Javiera Núñez", "javiera-nunez")
    for q in ("nunez", "NÚÑEZ", "Javiera Nu"):
        assert _grupos(client, q) == {"Personas": [("Javiera Núñez", "Integrante")]}, q


def test_una_firma_aparece_solo_si_tiene_algo_publicado(client, make_article):
    """Una firma sin nada publicado no tiene qué enseñar en su página."""
    from apps.content.models import EditorialStatus
    from apps.people.models import Contributor

    con_obra = Contributor.objects.create(display_name="Diego Salinas", slug="diego")
    sin_obra = Contributor.objects.create(display_name="Diego Borrador", slug="diego-b")
    make_article(status=EditorialStatus.PUBLISHED).authors.add(con_obra)
    make_article(status=EditorialStatus.DRAFT).authors.add(sin_obra)
    assert _grupos(client, "diego") == {"Personas": [("Diego Salinas", "Colaborador")]}
    html = client.get(BUSCAR, {"q": "diego"}).content.decode()
    assert f'href="{reverse("content:contributor_detail", args=["diego"])}"' in html


def test_lo_que_no_esta_publicado_no_aparece(client):
    from tests.factories import make_event, make_publication, make_recording

    make_recording(slug="r-oculto", title="Faro oculto", published=False)
    make_publication(slug="p-oculta", title="Faro oculto", published=False)
    make_event(slug="e-oculto", title="Faro oculto", published=False)
    assert _grupos(client, "faro oculto") == {}


def test_los_grupos_van_en_su_orden_y_con_su_dato(client, make_poem):
    from tests.factories import make_publication

    make_publication(slug="umbral-libro", title="Umbral", kind="plaquette", year=2022)
    _publish(make_poem(slug="umbral-poema", title="Umbral", body="la casa guarda un idioma"))
    _integrante("Ana Umbral", "ana-umbral")
    grupos = _grupos(client, "umbral")
    assert list(grupos) == ["Personas", "Poemas", "Publicaciones"]
    assert grupos["Publicaciones"] == [("Umbral", "Plaquette · 2022")]
    assert grupos["Poemas"] == [("Umbral", "")]


def test_el_panel_adelanta_cinco_por_grupo_y_la_pagina_diez(client):
    for n in range(12):
        _integrante(f"Poeta Número {n:02}", f"poeta-{n:02}")
    assert len(_grupos(client, "poeta", panel=True)["Personas"]) == 5
    assert len(_grupos(client, "poeta")["Personas"]) == 10


def test_una_letra_sola_no_busca_por_nombre(client):
    """Casaría con casi todos los nombres: no dice nada."""
    _integrante("Ana Pérez", "ana")
    assert "Personas" not in _grupos(client, "a")


def test_los_comodines_no_se_cuelan_en_la_busqueda_por_nombre(client):
    """`%` y `_` se buscan como letras: no casan con todo."""
    _integrante("Ana Pérez", "ana")
    for q in ("%%", "__", "%a%"):
        assert "Personas" not in _grupos(client, q), q


def test_un_titulo_con_etiquetas_se_escapa(client):
    from tests.factories import make_event

    make_event(slug="xss", title="<script>alert(1)</script> recital")
    html = client.get(BUSCAR, {"q": "recital"}).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; recital" in html


def test_los_cuatro_tipos_por_nombre_son_una_sola_consulta(client):
    """Unidos (UNION ALL), cada uno con su tope: con una consulta por tipo, la búsqueda
    pasaba de su techo. Y el coste no crece con lo que encuentra."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from tests.factories import make_event, make_publication, make_recording

    def consultas():
        with CaptureQueriesContext(connection) as capturadas:
            client.get(BUSCAR, {"q": "faro"})
        return [q["sql"] for q in capturadas if "UNION" in q["sql"]]

    def sembrar(n):
        _integrante(f"Faro {n}", f"faro-{n}")
        make_recording(slug=f"faro-r{n}", title=f"Faro {n}")
        make_publication(slug=f"faro-p{n}", title=f"Faro {n}")
        make_event(slug=f"faro-e{n}", title=f"Faro {n}")

    sembrar(0)
    pocas = consultas()
    for n in range(1, 12):
        sembrar(n)
    muchas = consultas()
    assert len(pocas) == len(muchas) == 1
    assert muchas[0].count("UNION ALL") == 3
    assert muchas[0].count("LIMIT 10") == 4, "cada tipo lleva su tope en el SQL"


def _result_titles(resp):
    sopa = BeautifulSoup(resp.content, "html.parser")
    return [a.get_text() for a in sopa.select(".search-list li > a")]


def test_search_puts_the_most_relevant_text_first(client, make_article):
    """El que nombra el término en el título y lo repite sale antes que el que lo menciona
    una vez, aunque este se publicara antes y la base lo devuelva primero."""
    _publish(
        make_article(
            slug="mencion", title="Diario de costa", body="Vimos una ballena. " + "mar " * 80
        )
    )
    _publish(
        make_article(
            slug="tema", title="La ballena", body="La ballena canta. La ballena vuelve. " * 5
        )
    )
    titles = _result_titles(client.get(reverse("content:search"), {"q": "ballena"}))
    assert titles == ["La ballena", "Diario de costa"]


def test_search_puts_the_most_relevant_poem_first(client):
    for slug, title, body in [
        ("mencion", "Orilla", "Pasó una ballena\n" + "agua\n" * 40),
        ("tema", "Ballena", "ballena de sal\nballena de sombra\nballena\n" * 3),
    ]:
        Poem.objects.create(
            slug=slug, title=title, body=body, status=S.PUBLISHED, published_at=timezone.now()
        )
    titles = _result_titles(client.get(reverse("content:search"), {"q": "ballena"}))
    assert titles == ["Ballena", "Orilla"]
