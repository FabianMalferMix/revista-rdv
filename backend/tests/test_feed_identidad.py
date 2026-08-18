"""El RSS de textos anuncia la identidad configurada, no una escrita a fuego.

`LatestArticlesFeed` llevaba «Reseñas — Revista literaria» como atributo de clase, de
cuando el proyecto era una revista de reseñas y no un colectivo de poesía. Al no consultar
`SiteProfile`, configurar la identidad en el panel —que está anotado como pendiente— no
habría cambiado el feed: el desajuste habría sobrevivido en silencio justo a la tarea
pensada para arreglarlo. Y quien lee un RSS es prensa y gestores, la audiencia del sitio.
"""

import pytest
from django.test import Client

from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db


def _canal(cliente=None):
    """Título y descripción del <channel>, tal como salen por HTTP."""
    xml = (cliente or Client()).get("/feed/").content.decode()
    canal = xml.split("<channel>", 1)[1]
    corta = lambda etiqueta: canal.split(f"<{etiqueta}>", 1)[1].split(f"</{etiqueta}>", 1)[0]  # noqa: E731
    return corta("title"), corta("description")


def test_el_titulo_sale_del_perfil_no_del_codigo():
    perfil = SiteProfile.load()
    perfil.name = "Casa Tomada"
    perfil.tagline = "Colectivo de poesía"
    perfil.save()

    titulo, descripcion = _canal()
    assert titulo == "Casa Tomada — Colectivo de poesía"
    assert descripcion == "Colectivo de poesía"


def test_no_queda_rastro_de_la_identidad_antigua():
    """La prueba que habría detectado esto: ninguna cadena fija del pasado en el feed."""
    perfil = SiteProfile.load()
    perfil.name = "Casa Tomada"
    perfil.tagline = "Colectivo de poesía"
    perfil.save()

    titulo, descripcion = _canal()
    assert "Revista literaria" not in titulo + descripcion


def test_sin_lema_no_deja_un_guion_suelto():
    perfil = SiteProfile.load()
    perfil.name = "Casa Tomada"
    perfil.tagline = ""
    perfil.save()

    titulo, descripcion = _canal()
    assert titulo == "Casa Tomada"
    assert not titulo.endswith("—")
    # Sin lema el feed tampoco puede quedarse mudo.
    assert descripcion


def test_el_feed_sigue_sirviendo_los_articulos():
    """Contra-prueba: cambiar el encabezado no debe romper el contenido."""
    from apps.content.models import Article, EditorialStatus

    Article.objects.create(slug="uno", title="Un texto publicado", status=EditorialStatus.PUBLISHED)
    xml = Client().get("/feed/").content.decode()
    assert "Un texto publicado" in xml
