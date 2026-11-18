"""Cada dirección responde solo a los métodos que tienen sentido en ella.

Las páginas, los archivos, los feeds, el sitemap y las sondas son de lectura: GET y HEAD. Los
formularios aceptan además POST: el alta al boletín, solo POST. Cualquier otro método da 405, con
la cabecera Allow que dice cuáles valen. El panel tiene sus propias reglas y no entra.
"""

import re

import pytest
from django.urls import URLResolver, get_resolver
from django.views.static import serve

pytestmark = pytest.mark.django_db

READ = ["GET", "HEAD"]
# Los formularios, con los métodos que aceptan: el GET de la confirmación, de la baja y del envío
# enseña el formulario, y el POST es lo que cambia algo.
FORMS = {
    "community:subscribe": ["POST"],
    "community:confirm": ["GET", "HEAD", "POST"],
    "community:unsubscribe": ["GET", "HEAD", "POST"],
    "submissions:submit": ["GET", "HEAD", "POST"],
}
OTHERS = ["POST", "PUT", "PATCH", "DELETE"]


def _routes():
    """(dirección, nombre) de cada ruta fuera del panel, también las que no tienen nombre (las
    direcciones viejas que redirigen), con un valor de prueba en cada parámetro."""
    routes = []

    def walk(patterns, prefix, namespace):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                if pattern.app_name != "admin":
                    inner = ":".join(filter(None, [namespace, pattern.namespace]))
                    walk(pattern.url_patterns, prefix + str(pattern.pattern), inner)
            # Lo que sirve los archivos subidos con DEBUG (`static()`): una ayuda de desarrollo,
            # fuera del sitio.
            elif pattern.callback is not serve:
                name = pattern.name and ":".join(filter(None, [namespace, pattern.name]))
                route = re.sub(r"<int:\w+>", "1", prefix + str(pattern.pattern))
                routes.append((re.sub(r"<(?:\w+:)?\w+>", "x", route), name))

    walk(get_resolver().url_patterns, "/", None)
    return routes


ROUTES = _routes()


def test_the_walk_sees_every_kind_of_route():
    """Control del recorrido: ve las fichas con su parámetro, los formularios y las direcciones
    viejas sin nombre."""
    assert ("/textos/", "content:text_archive") in ROUTES
    assert ("/envios/1/archivo/", "submissions:file") in ROUTES
    assert set(FORMS) <= {name for _, name in ROUTES}
    assert ("/archivo/publicacion/x/x", None) in ROUTES


@pytest.mark.parametrize(("url", "name"), ROUTES, ids=[url for url, _ in ROUTES])
def test_each_route_answers_only_its_methods(client, url, name):
    allowed = FORMS.get(name, READ)
    for method in ["GET", "HEAD", *OTHERS]:
        response = client.generic(method, url)
        if method in allowed:
            assert response.status_code != 405, method
        else:
            assert response.status_code == 405, method
            assert response["Allow"] == ", ".join(allowed), method
