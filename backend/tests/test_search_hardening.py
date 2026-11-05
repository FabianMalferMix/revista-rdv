"""Endurecimiento del buscador FTS (hallazgo S-04).

Era el endpoint público más caro del sitio y el único sin control anti-abuso: sin
`LIMIT` en SQL (el recorte a 10 se hacía en Python tras materializar todas las filas
que casaban, con el cuerpo entero de cada pieza), sin rate limit y con un 500 público
alcanzable con `?q=%00`.
"""

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from tests.factories import make_article

pytestmark = pytest.mark.django_db
BUSCAR = reverse("content:search")


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
    from apps.content.views import SEARCH_MAX_QUERY

    with CaptureQueriesContext(connection) as queries:
        resp = client.get(BUSCAR, {"q": "a" * 5000})
    assert resp.status_code == 200
    sql = "\n".join(q["sql"] for q in queries)
    assert "a" * SEARCH_MAX_QUERY in sql  # control: la consulta llegó a la base
    assert "a" * (SEARCH_MAX_QUERY + 1) not in sql


def test_la_consulta_se_recorta_a_la_longitud_maxima(client):
    """Una búsqueda larga sigue buscando con lo que cabe en el tope. La cola que pasa del tope
    nombra una palabra que el texto no tiene, y aun así lo encuentra: no cuenta."""
    from apps.content.views import SEARCH_MAX_QUERY

    article = make_article(title="Umbral", body="Un verso y otro verso.", status="published")
    head = "umbral"
    while len(head) + len(" verso") <= SEARCH_MAX_QUERY:
        head += " verso"
    long_query = head.ljust(SEARCH_MAX_QUERY) + " inexistente" * 20
    assert len(long_query) > SEARCH_MAX_QUERY
    resp = client.get(BUSCAR, {"q": long_query})
    assert resp.status_code == 200
    assert f'href="{article.get_absolute_url()}"'.encode() in resp.content


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
    assert ultima.status_code == 200
    assert "Demasiadas búsquedas".encode() in ultima.content


@override_settings(RATELIMIT_ENABLE=True)
def test_the_panel_announces_the_limit_as_well(client, frozen_rate_limit_window):
    """En el panel de la lupa, el aviso llega también a la región que se anuncia: los
    resultados ya no son una región viva."""
    from bs4 import BeautifulSoup

    make_article(title="Umbral", status="published")
    for i in range(65):
        ultima = client.get(BUSCAR, {"q": f"umbral {i}"}, headers={"HX-Request": "true"})
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


def _search_queries(client, method):
    with CaptureQueriesContext(connection) as consultas:
        respuesta = getattr(client, method)(BUSCAR, {"q": "umbral"})
    assert respuesta.status_code == 200
    return [c["sql"] for c in consultas.captured_queries if "plainto_tsquery" in c["sql"]]


def test_head_counts_towards_the_search_limit(client, frozen_rate_limit_window):
    """Tras 61 GET, un HEAD no ejecuta ninguna búsqueda: Django corre la vista entera también
    en HEAD, y antes el límite solo contaba los GET. Control: antes del límite, el mismo
    HEAD sí busca."""
    make_article(title="Umbral", status="published")
    assert _search_queries(client, "head")
    for i in range(61):
        client.get(BUSCAR, {"q": f"umbral {i}"})
    assert _search_queries(client, "head") == []


def test_search_only_answers_safe_methods(client):
    assert client.get(BUSCAR, {"q": "umbral"}).status_code == 200
    assert client.post(BUSCAR, {"q": "umbral"}).status_code == 405
