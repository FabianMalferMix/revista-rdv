"""El pie con la identidad del colectivo y los enlaces que faltaban entre fichas
(backlog UX, tickets 4.4 y 4.5).

El pie era un formulario y un mapa de enlaces: al llegar al final de una página no decía
de quién era. Ahora lo abre la identidad del colectivo (el sello, de dónde es y desde
cuándo, el correo y el Instagram), y el mapa ya no repite el correo ni el Instagram. La
ficha de una integrante enseña ahora las actividades en que participó.
"""

from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.people.models import Contributor
from apps.showcase.models import SiteProfile, SiteSocialLink
from tests.factories import make_event

pytestmark = pytest.mark.django_db


def _sopa(client, url):
    return BeautifulSoup(client.get(url).content, "html.parser")


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
    pie = _sopa(client, reverse("content:poem_index")).select_one("footer.site-foot")
    identidad = pie.select_one(".foot-identidad")
    assert identidad.select_one("a.brand")["href"] == reverse("content:home")
    assert identidad.select_one(".foot-presentacion").get_text() == (
        "Colectivo de poesía · Chile · desde 2023"
    )
    contacto = {a.get_text(): a["href"] for a in identidad.select(".foot-contacto a")}
    assert contacto == {
        "hola@example.com": "mailto:hola@example.com",
        "Instagram @repitentesdelverso": "https://www.instagram.com/repitentesdelverso/",
    }
    # El orden del ticket: la identidad, el mapa, el boletín y lo legal.
    piezas = [hijo["class"][0] for hijo in pie.select_one(".wrap-wide").find_all(recursive=False)]
    assert piezas == ["foot-identidad", "foot-groups", "newsletter", "foot-legal"], (
        "el orden del marcado es el que se ve y el del tabulador"
    )


def test_el_mapa_del_pie_no_repite_el_correo_ni_el_instagram(client, perfil):
    """Ya van en la identidad. El menú del teléfono, que no la tiene, los conserva."""
    sopa = _sopa(client, reverse("content:poem_index"))
    pie = sopa.select_one("footer.site-foot .foot-groups")
    menu = sopa.select_one("header .menu-mapa .foot-groups")
    for mapa, los_lleva in ((pie, False), (menu, True)):
        hrefs = [a["href"] for a in mapa.select("a")]
        assert ("mailto:hola@example.com" in hrefs) is los_lleva
        assert ("https://www.instagram.com/repitentesdelverso/" in hrefs) is los_lleva


def test_aliados_se_titula_como_el_enlace_que_lleva_a_ella(client):
    """El pie, la barra del colectivo y el cierre de la portada la llaman «Aliados»; su
    título decía «Aliados y financiamiento» (la bajada ya habla de los fondos)."""
    assert _sopa(client, reverse("showcase:partner_index")).h1.get_text(strip=True) == "Aliados"


def test_la_ficha_de_una_integrante_lleva_sus_actividades(client):
    """Las más recientes primero; un evento sin publicar no sale."""
    fernanda = Contributor.objects.create(slug="fernanda", display_name="Fernanda", is_member=True)
    ahora = timezone.now()
    vieja = make_event(slug="vieja", title="Lectura vieja", starts_at=ahora - timedelta(days=90))
    reciente = make_event(
        slug="reciente", title="Recital reciente", starts_at=ahora - timedelta(days=9)
    )
    oculta = make_event(slug="oculta", title="Borrador", published=False)
    otra = make_event(slug="otra", title="De otra persona")
    for evento in (vieja, reciente, oculta):
        evento.participants.add(fernanda)
    assert otra.participants.count() == 0
    sopa = _sopa(client, fernanda.get_absolute_url())
    seccion = next(s for s in sopa.select("article section") if s.h2.get_text() == "Actividades")
    assert [a.get_text() for a in seccion.select("li > a")] == ["Recital reciente", "Lectura vieja"]
