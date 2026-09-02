"""Article, Page y Collection saben decir dónde viven.

Sin `get_absolute_url`, el admin de Django no ofrece el botón «Ver en el sitio» en la
ficha: quien acaba de publicar no tiene forma de saltar a la página pública y tiene que
componer la URL de memoria. Y aquí adivinarla falla, porque el slug de un artículo se
deriva de la obra reseñada, no de su título —le pasó a quien escribió estas pruebas—.
Poem, Event, Publication y Recording ya lo tenían; estos tres se habían quedado fuera.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import Client

from apps.content.models import Article, Collection, EditorialStatus, Page, PublishStatus

pytestmark = pytest.mark.django_db


def _articulo(**extra):
    return Article.objects.create(
        title="Un texto", slug="un-texto", status=EditorialStatus.PUBLISHED, **extra
    )


def test_las_tres_urls_apuntan_a_su_ruta():
    a = _articulo()
    c = Collection.objects.create(title="Una colección", slug="una-coleccion")
    p = Page.objects.create(title="Una página", slug="una-pagina")
    assert a.get_absolute_url() == "/articulo/un-texto/"
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
    assert respuesta["Location"].endswith("/articulo/un-texto/")


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
    )
    assert a.get_absolute_url() == "/articulo/otro/"
    esperado = 404 if borrador else 200
    assert Client().get(a.get_absolute_url()).status_code == esperado


def test_el_sitemap_sigue_respondiendo():
    """Contra-prueba: los sitemaps resolvían con reverse(); añadir el método no los rompe."""
    _articulo()
    Page.objects.create(title="P", slug="p", status=PublishStatus.PUBLISHED)
    assert Client().get("/sitemap.xml").status_code == 200
