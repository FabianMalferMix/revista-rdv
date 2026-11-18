"""El RSS de textos anuncia la identidad del perfil del sitio, no una escrita en el código.

`LatestArticlesFeed` lee el nombre y el lema de `SiteProfile`: cambiarlos en el panel cambia
también el feed. Y quien lee un RSS es prensa y gestores, la audiencia del sitio.
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
