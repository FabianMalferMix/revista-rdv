"""Endurecimiento del buscador FTS (hallazgo S-04).

Era el endpoint público más caro del sitio y el único sin control anti-abuso: sin
`LIMIT` en SQL (el recorte a 10 se hacía en Python tras materializar todas las filas
que casaban, con el cuerpo entero de cada pieza), sin rate limit y con un 500 público
alcanzable con `?q=%00`.
"""

import re

import pytest
from bs4 import BeautifulSoup
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.site.views import SEARCH_MAX_QUERY
from tests.factories import (
    SEARCH_PANEL_HEADERS,
    make_article,
    make_published_article,
    make_published_poem,
    soup,
)

pytestmark = pytest.mark.django_db
BUSCAR = reverse("site:search")


def test_byte_nul_no_provoca_un_500(client):
    """`GET /buscar/?q=%00` reventaba con DataError de psycopg (PostgreSQL no admite
    NUL en campos de texto): 500 público alcanzable por cualquier anónimo."""
    resp = client.get(BUSCAR, {"q": "\x00"})
    assert resp.status_code == 200


def test_byte_nul_intercalado_tampoco_rompe(client):
    make_article(title="Umbral", status="published")
    resp = client.get(BUSCAR, {"q": "umb\x00ral"})
    assert resp.status_code == 200


def test_consulta_desmesurada_se_trunca(client):
    """A la base llegan solo los primeros SEARCH_MAX_QUERY caracteres de la consulta."""
    with CaptureQueriesContext(connection) as queries:
        resp = client.get(BUSCAR, {"q": "a" * 5000})
    assert resp.status_code == 200
    sql = "\n".join(q["sql"] for q in queries)
    assert "a" * SEARCH_MAX_QUERY in sql  # control: la consulta llegó a la base
    assert "a" * (SEARCH_MAX_QUERY + 1) not in sql


# Lo que la búsqueda le pide a la base, tal como llega en el SQL: el texto de cada
# `plainto_tsquery` (textos y poemas) y el que se compara con los nombres (`UNACCENT`).
SEARCHED_IN_SQL = re.compile(
    r"(plainto_tsquery|UNACCENT)\((?:'[^']*'::regconfig,)?\s*E?'((?:[^']|'')*)'"
)

# Un verso largo, como se pega desde el poema. El tope cae dentro de «muelle», y lo que cabe de
# esa palabra, «mu», no está en el poema ni en el texto que lo cita.
VERSE = (
    "El faro gira su luz sobre el mar dormido y nombra uno por uno los barcos que no volverán, "
    "mientras la niebla borra el muelle y las gaviotas callan."
)
WHOLE_WORDS = VERSE[: VERSE.index(" muelle")]


@pytest.mark.parametrize("panel", [False, True], ids=["page", "panel"])
def test_a_long_verse_finds_its_poem_although_the_cap_splits_a_word(client, panel):
    """Pegar un verso de más de SEARCH_MAX_QUERY caracteres encuentra el poema que lo contiene y
    el texto que lo cita, aunque el tope caiga dentro de una palabra: esa palabra queda fuera
    entera, y a la base llegan solo las palabras enteras que caben, por los dos caminos (el
    texto completo y los nombres). La página y el panel dicen eso que se buscó."""
    assert VERSE[:SEARCH_MAX_QUERY] == f"{WHOLE_WORDS} mu"  # el tope parte «muelle»
    poem = make_published_poem(title="Faro", body=f"{VERSE}\nY vuelve la luz.")
    article = make_published_article(
        title="Notas de lectura", body=f"<p>Leímos «{VERSE}» en voz alta.</p>"
    )
    headers = SEARCH_PANEL_HEADERS if panel else {}
    with CaptureQueriesContext(connection) as queries:
        response = client.get(BUSCAR, {"q": VERSE}, headers=headers)
    assert response.status_code == 200
    html = BeautifulSoup(response.content, "html.parser")
    found = [link["href"] for link in html.select(".search-list a")]
    assert found == [poem.get_absolute_url(), article.get_absolute_url()]
    if panel:
        status = html.select_one("#search-status").get_text()
        assert status == f"2 resultados para “{WHOLE_WORDS}”"
    else:
        assert html.select_one("#q-page")["value"] == WHOLE_WORDS
        summary = html.select_one(".search-summary").get_text()
        assert summary == f"Resultados para «{WHOLE_WORDS}»"
    searched = [match for query in queries for match in SEARCHED_IN_SQL.findall(query["sql"])]
    assert {path for path, _ in searched} == {"plainto_tsquery", "UNACCENT"}
    assert {text for _, text in searched} == {WHOLE_WORDS}
    assert max(len(text) for _, text in searched) <= SEARCH_MAX_QUERY


# 29 «luz» y su espacio son 116 caracteres: la palabra de cuatro letras que siga acaba justo en
# el tope. LUZ_WORDS es lo que queda si el tope la parte.
LUZ = "luz " * 29
LUZ_WORDS = LUZ.rstrip()
FULL = f"{LUZ}faro"


@pytest.mark.parametrize(
    ("written", "searched"),
    [
        pytest.param(FULL, FULL, id="the_cap_exactly"),
        pytest.param(f"{FULL} niebla", FULL, id="cut_on_a_space"),
        pytest.param(f"{LUZ}luz faro", f"{LUZ}luz", id="cut_after_a_space"),
        pytest.param(f"{FULL}s niebla", LUZ_WORDS, id="cut_inside_a_word"),
        pytest.param(f"{FULL}, niebla", LUZ_WORDS, id="punctuation_goes_with_its_word"),
        pytest.param(f"{LUZ}café niebla", f"{LUZ}café", id="an_accented_letter_counts_once"),
        # «café» con la tilde aparte (U+0301), como llega de algunos PDF: son cinco caracteres,
        # y el tope cae entre la «e» y su tilde.
        pytest.param(f"{LUZ}cafe\u0301 niebla", LUZ_WORDS, id="a_combining_accent"),
        pytest.param(f"{LUZ_WORDS}\u00a0faros niebla", LUZ_WORDS, id="a_non_breaking_space"),
        pytest.param(f"{LUZ_WORDS}   faros niebla", LUZ_WORDS, id="repeated_spaces"),
        pytest.param(f"   {FULL}   niebla   ", FULL, id="spaces_at_the_edges"),
        pytest.param("luz" * 50, ("luz" * 50)[:SEARCH_MAX_QUERY], id="no_space_within_the_cap"),
    ],
)
def test_the_search_field_shows_what_was_searched(client, written, searched):
    """Sin aviso aparte: el campo de la página enseña la consulta tal como se buscó. El tope solo
    se lleva la palabra que parte, con su puntuación y los espacios que la preceden; si cae en un
    espacio, o justo después de uno, no se pierde nada. Los espacios de los bordes no cuentan
    para el tope, la tilde es parte de la palabra y una consulta sin espacios se corta en el
    tope."""
    assert len(FULL) == SEARCH_MAX_QUERY
    page = soup(client, BUSCAR, data={"q": written})
    assert page.select_one("#q-page")["value"] == searched


def test_el_limit_viaja_al_sql(client):
    """El recorte a 10 se hacía en Python DESPUÉS de materializar todas las filas: el
    SQL salía sin LIMIT. Se comprueba en el SQL emitido, que es donde importa."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    for i in range(25):
        make_article(title=f"Umbral numero {i}", status="published")
    with CaptureQueriesContext(connection) as capturadas:
        resp = client.get(BUSCAR, {"q": "umbral"})
    assert resp.status_code == 200

    consultas_fts = [q["sql"] for q in capturadas if "search_vector" in q["sql"]]
    assert consultas_fts, "no se emitió ninguna consulta de búsqueda"
    for sql in consultas_fts:
        assert "LIMIT 10" in sql, f"consulta FTS sin LIMIT: {sql[:200]}"
    # Acotado a la lista de resultados: contar <li> en toda la página medía también el
    # mapa del sitio del pie, que tiene los suyos. La aserción parecía sobre la búsqueda
    # y era sobre la plantilla entera.
    import re

    lista = re.search(rb'<ul class="search-list">.*?</ul>', resp.content, re.S)
    assert lista, "no se renderizó la lista de resultados"
    assert lista.group(0).count(b"<li>") <= 10


def test_el_coste_no_crece_con_el_tamano_del_archivo(client):
    """Invariante que cierra el vector de amplificación: la misma consulta debe costar
    lo mismo con 5 piezas que con 30."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def consultas_fts():
        with CaptureQueriesContext(connection) as capturadas:
            client.get(BUSCAR, {"q": "umbral"})
        return [q for q in capturadas if "search_vector" in q["sql"]]

    for i in range(5):
        make_article(title=f"Umbral numero {i}", status="published")
    pocas = consultas_fts()

    for i in range(5, 30):
        make_article(title=f"Umbral numero {i}", status="published")
    muchas = consultas_fts()

    # Dos consultas acotadas (artículos y poemas), sea cual sea el tamaño del archivo.
    # No se compara el total de consultas de la petición: varía con cachés calientes.
    assert len(pocas) == len(muchas) == 2


@override_settings(RATELIMIT_ENABLE=True)
def test_el_buscador_limita_por_ip(client, frozen_rate_limit_window):
    """Supera el cupo (60/m) y comprueba que degrada con un aviso, no con un 500 ni
    sirviendo consultas ilimitadas."""
    make_article(title="Umbral", status="published")
    ultima = None
    for i in range(65):
        ultima = client.get(BUSCAR, {"q": f"umbral {i}"})
    assert ultima.status_code == 429
    assert "Demasiadas búsquedas".encode() in ultima.content


@override_settings(RATELIMIT_ENABLE=True)
def test_the_panel_announces_the_limit_as_well(client, frozen_rate_limit_window):
    """En el panel de la lupa, el aviso llega también a la región que se anuncia: los
    resultados ya no son una región viva. Llega con un 200, porque htmx no pinta una
    respuesta de error."""
    from bs4 import BeautifulSoup

    make_article(title="Umbral", status="published")
    for i in range(65):
        ultima = client.get(BUSCAR, {"q": f"umbral {i}"}, headers=SEARCH_PANEL_HEADERS)
    assert ultima.status_code == 200
    assert "Retry-After" not in ultima
    estado = BeautifulSoup(ultima.content, "html.parser").select_one("#search-status")
    assert estado.get_text() == (
        "Demasiadas búsquedas seguidas. Espera un momento e inténtalo de nuevo."
    )


@override_settings(RATELIMIT_ENABLE=True)
def test_el_limite_no_estorba_al_uso_normal(client, frozen_rate_limit_window):
    """El buscador en vivo dispara una petición por pulsación (con 300 ms de rebote):
    una ráfaga humana razonable no puede quedar bloqueada."""
    article = make_article(title="Umbral", status="published")
    for _ in range(20):
        resp = client.get(BUSCAR, {"q": "umbral"})
    assert "Demasiadas búsquedas".encode() not in resp.content
    # Control: la vigésima búsqueda encuentra el texto.
    assert f'href="{article.get_absolute_url()}"'.encode() in resp.content


def _search_queries(client, method, status=200):
    with CaptureQueriesContext(connection) as consultas:
        respuesta = getattr(client, method)(BUSCAR, {"q": "umbral"})
    assert respuesta.status_code == status
    return [c["sql"] for c in consultas.captured_queries if "plainto_tsquery" in c["sql"]]


def test_head_counts_towards_the_search_limit(client, frozen_rate_limit_window):
    """Tras 61 GET, un HEAD no ejecuta ninguna búsqueda: Django corre la vista entera también
    en HEAD, y antes el límite solo contaba los GET. Control: antes del límite, el mismo
    HEAD sí busca."""
    make_article(title="Umbral", status="published")
    assert _search_queries(client, "head")
    for i in range(61):
        client.get(BUSCAR, {"q": f"umbral {i}"})
    assert _search_queries(client, "head", status=429) == []


def test_search_only_answers_safe_methods(client):
    assert client.get(BUSCAR, {"q": "umbral"}).status_code == 200
    assert client.post(BUSCAR, {"q": "umbral"}).status_code == 405


def test_a_search_that_fails_midway_shows_no_half_results_and_the_page_whole(client, monkeypatch):
    """Si la consulta por nombre se cancela por su plazo cuando los textos y los poemas ya se
    leyeron, la página dice «sin resultados», sin la mitad de ellos, y se pinta entera: el
    fallo deshace solo el bloque de la búsqueda, y la página sigue consultando la base para
    pintar el resto. Control: sin el fallo, el texto aparece."""
    article = make_published_article(title="Umbral del verso")
    found = soup(client, BUSCAR, data={"q": "umbral"})
    assert [a["href"] for a in found.select(".search-list a")] == [article.get_absolute_url()]

    def cancelled_by_its_timeout(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = 1")
            cursor.execute("SELECT pg_sleep(1)")
        return []

    monkeypatch.setattr("apps.site.views.coincidencias_por_nombre", cancelled_by_its_timeout)
    page = soup(client, BUSCAR, data={"q": "umbral"})
    assert page.select(".search-list a") == []
    assert page.select_one(".empty").get_text() == "Sin resultados para “umbral”."
    assert page.select_one("footer") is not None
