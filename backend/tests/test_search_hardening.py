"""Endurecimiento del buscador FTS (hallazgo S-04).

Era el endpoint público más caro del sitio y el único sin control anti-abuso: sin
`LIMIT` en SQL (el recorte a 10 se hacía en Python tras materializar todas las filas
que casaban, con el cuerpo entero de cada pieza), sin rate limit y con un 500 público
alcanzable con `?q=%00`.
"""

import pytest
from django.test import override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db
BUSCAR = reverse("content:search")


def test_byte_nul_no_provoca_un_500(client):
    """`GET /buscar/?q=%00` reventaba con DataError de psycopg (PostgreSQL no admite
    NUL en campos de texto): 500 público alcanzable por cualquier anónimo."""
    resp = client.get(BUSCAR, {"q": "\x00"})
    assert resp.status_code == 200


def test_byte_nul_intercalado_tampoco_rompe(client, make_article):
    make_article(title="Umbral", status="published")
    resp = client.get(BUSCAR, {"q": "umb\x00ral"})
    assert resp.status_code == 200


def test_consulta_desmesurada_se_trunca(client):
    resp = client.get(BUSCAR, {"q": "a" * 5000})
    assert resp.status_code == 200


def test_la_consulta_se_recorta_a_la_longitud_maxima(client, make_article):
    """El truncado no debe romper una búsqueda legítima larga."""
    from apps.content.views import SEARCH_MAX_QUERY

    make_article(title="Umbral", status="published")
    larga = "umbral" + " x" * 200
    assert len(larga) > SEARCH_MAX_QUERY
    resp = client.get(BUSCAR, {"q": larga})
    assert resp.status_code == 200


def test_el_limit_viaja_al_sql(client, make_article):
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
    assert resp.content.count(b"<li>") <= 10


def test_el_coste_no_crece_con_el_tamano_del_archivo(client, make_article):
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
def test_el_buscador_limita_por_ip(client, make_article):
    """Supera el cupo (60/m) y comprueba que degrada con un aviso, no con un 500 ni
    sirviendo consultas ilimitadas."""
    make_article(title="Umbral", status="published")
    ultima = None
    for i in range(65):
        ultima = client.get(BUSCAR, {"q": f"umbral {i}"})
    assert ultima.status_code == 200
    assert "Demasiadas búsquedas".encode() in ultima.content


@override_settings(RATELIMIT_ENABLE=True)
def test_el_limite_no_estorba_al_uso_normal(client, make_article):
    """El buscador en vivo dispara una petición por pulsación (con 300 ms de rebote):
    una ráfaga humana razonable no puede quedar bloqueada."""
    make_article(title="Umbral", status="published")
    for _ in range(20):
        resp = client.get(BUSCAR, {"q": "umbral"})
    assert "Demasiadas búsquedas".encode() not in resp.content
