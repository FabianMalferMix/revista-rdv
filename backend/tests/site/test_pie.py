"""El pie con la identidad del colectivo.

Lo abre la identidad del colectivo (el sello, de dónde es y desde cuándo, el correo y el
Instagram): al llegar al final de una página, se sabe de quién es. El mapa no repite el correo
ni el Instagram. Enlaza a las páginas de privacidad y de cookies, con la nota de consentimiento
del boletín.
"""

import pytest
from django.urls import reverse

from apps.showcase.models import SiteProfile, SiteSocialLink
from tests.factories import soup

pytestmark = pytest.mark.django_db


@pytest.fixture
def perfil(db):
    perfil = SiteProfile.load()
    perfil.name = "Repitentes del Verso"
    perfil.tagline = "Colectivo de poesía"
    perfil.location = "Chile"
    perfil.founded_year = 2023
    perfil.general_email = "hola@example.com"
    perfil.save()
    SiteSocialLink.objects.create(
        profile=perfil, platform="Instagram", url="https://www.instagram.com/repitentesdelverso/"
    )
    return perfil


def test_el_pie_empieza_por_la_identidad_del_colectivo(client, perfil):
    pie = soup(client, reverse("content:poem_index")).select_one("footer.site-foot")
    identidad = pie.select_one(".foot-identidad")
    assert identidad.select_one("a.brand")["href"] == reverse("site:home")
    assert identidad.select_one(".foot-presentacion").get_text() == (
        "Colectivo de poesía · Chile · desde 2023"
    )
    contacto = {a.get_text(): a["href"] for a in identidad.select(".foot-contacto a")}
    assert contacto == {
        "hola@example.com": "mailto:hola@example.com",
        "Instagram @repitentesdelverso": "https://www.instagram.com/repitentesdelverso/",
    }
    # El orden: la identidad, el mapa, el boletín y lo legal.
    piezas = [hijo["class"][0] for hijo in pie.select_one(".wrap-wide").find_all(recursive=False)]
    assert piezas == ["foot-identidad", "foot-groups", "newsletter", "foot-legal"], (
        "el orden del marcado es el que se ve y el del tabulador"
    )


def test_el_mapa_del_pie_no_repite_el_correo_ni_el_instagram(client, perfil):
    """Ya van en la identidad. El menú del teléfono, que no la tiene, los conserva."""
    sopa = soup(client, reverse("content:poem_index"))
    pie = sopa.select_one("footer.site-foot .foot-groups")
    menu = sopa.select_one("header .menu-mapa .foot-groups")
    for mapa, los_lleva in ((pie, False), (menu, True)):
        hrefs = [a["href"] for a in mapa.select("a")]
        assert ("mailto:hola@example.com" in hrefs) is los_lleva
        assert ("https://www.instagram.com/repitentesdelverso/" in hrefs) is los_lleva


def test_the_phone_menu_ends_press_and_management_with_the_contact_address(client, perfil):
    """En el menú del teléfono, el correo del colectivo cierra «Prensa y gestión», el grupo de
    quien gestiona, y no se repite en los demás."""
    menu = soup(client, reverse("content:poem_index")).select_one("header .menu-mapa .foot-groups")
    groups = {
        group.select_one(".foot-group-titulo").get_text(strip=True): [
            a["href"] for a in group.select("a")
        ]
        for group in menu.select(".foot-group")
    }
    mail = "mailto:hola@example.com"
    assert {title for title, hrefs in groups.items() if mail in hrefs} == {"Prensa y gestión"}
    assert groups["Prensa y gestión"][-1] == mail


def test_footer_has_legal_links_and_consent(client):
    content = client.get(reverse("site:home")).content
    assert reverse("content:page_detail", args=["privacidad"]).encode() in content
    assert reverse("content:page_detail", args=["cookies"]).encode() in content
    assert b"pol\xc3\xadtica de privacidad" in content  # nota de consentimiento del form
