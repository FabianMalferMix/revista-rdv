"""Las páginas 404 y 500 tienen identidad y, sobre todo, salida.

El 404 por defecto de Django son 179 bytes en inglés, sin cabecera, sin pie y sin un solo
enlace: quien llega desde una dirección rota se queda encerrado.

Las dos plantillas se tratan distinto A PROPÓSITO, y estas pruebas fijan el porqué:
`page_not_found` renderiza con `request` y con los procesadores de contexto, así que 404
puede extender base.html y traer la navegación entera; `server_error` renderiza SIN
contexto, y como el procesador `site_profile` hace `SiteProfile.load()` —una consulta—,
una página de 500 que heredara de base.html dependería de la base de datos justo en el
fallo que más veces la deja fuera.
"""

import pytest
from django.template import loader
from django.test import Client

pytestmark = pytest.mark.django_db


def _texto(html):
    import re

    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def test_el_404_responde_y_no_es_el_de_django():
    r = Client().get("/una-ruta-que-no-existe/")
    assert r.status_code == 404
    cuerpo = r.content.decode()
    assert len(cuerpo) > 1000, "sigue sirviéndose el 404 pelado de Django (179 bytes)"
    assert "Esta página no existe" in _texto(cuerpo)


def test_el_404_ofrece_salida():
    """Lo que de verdad arregla el deferido: que se pueda volver a alguna parte."""
    cuerpo = Client().get("/una-ruta-que-no-existe/").content.decode()
    for destino in ("/", "/textos/", "/poemas/", "/buscar/"):
        assert f'href="{destino}"' in cuerpo, f"falta la salida a {destino}"


def test_el_404_trae_la_navegacion_del_sitio():
    """Extiende base.html: cabecera, buscador y pie.

    El buscador se comprueba sobre el HTML y no sobre el texto visible: su rótulo vive en
    el atributo `placeholder`, y quitar las etiquetas se lleva los atributos con ellas.
    """
    html = Client().get("/una-ruta-que-no-existe/").content.decode()
    assert "Saltar al contenido" in _texto(html)
    assert 'class="masthead"' in html
    assert 'placeholder="Buscar textos' in html
    assert 'class="site-foot"' in html


def test_el_500_se_dibuja_sin_contexto_ni_base_de_datos(django_assert_num_queries):
    """La prueba que justifica que 500.html NO herede de base.html.

    Se renderiza como lo hace `server_error`: sin request y sin contexto. Si la plantilla
    dependiera de `site_profile`, esto dispararía una consulta —y en el escenario real, la
    base caída, la página de error fallaría a su vez.
    """
    with django_assert_num_queries(0):
        html = loader.get_template("500.html").render()
    texto = _texto(html)
    assert "Algo se rompió de nuestro lado" in texto
    assert 'href="/"' in html, "sin salida a la portada"


def test_el_500_no_lleva_estilos_ni_scripts_en_linea():
    """La CSP de producción es `style-src 'self'`: un style= inline no se aplicaría."""
    html = loader.get_template("500.html").render()
    assert "style=" not in html
    assert "<script" not in html


def test_el_500_pide_no_ser_indexado():
    assert 'name="robots" content="noindex"' in loader.get_template("500.html").render()
