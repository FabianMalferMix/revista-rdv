"""La obra de la portada se elige en el perfil del sitio, en el panel."""

import pytest
from django.urls import reverse

from apps.showcase.admin import SiteProfileAdmin
from apps.showcase.models import SiteProfile
from tests.factories import soup

pytestmark = pytest.mark.django_db


def test_la_obra_se_elige_desde_el_panel(client, django_user_model):
    """Los dos campos están en el perfil del sitio, con su nombre en castellano y el buscador
    de la biblioteca de imágenes, como la imagen para compartir."""
    assert {"hero_image", "hero_image_phone"} <= set(SiteProfileAdmin.autocomplete_fields)
    SiteProfile.load()
    client.force_login(django_user_model.objects.create_superuser("admin", "a@example.com", "x"))
    sopa = soup(client, reverse("admin:showcase_siteprofile_change", args=[1]))
    for campo, rotulo in (
        ("hero_image", "Imagen de portada"),
        ("hero_image_phone", "Imagen de portada para el teléfono"),
    ):
        assert sopa.select_one(f"select#id_{campo}") is not None
        assert sopa.select_one(f"label[for=id_{campo}]").get_text(strip=True).rstrip(":") == rotulo
