"""El titular de la portada (backlog UX, ticket 4.2; decisiones D8, D9 y D18).

El titular era el lema, «Colectivo de poesía», con el nombre escondido en un h1 para
lectores de pantalla. Después el nombre fue el titular, con el lema en la cejilla y un objeto
real al lado; el dueño del sitio quitó lo que iba debajo: las cifras, los aliados y la cita
de prensa. Con la portada como obra (D18, 2026-10-20) el nombre es el logo, al pie de la
obra, y lo demás pasa a la hoja que sigue, sin el objeto: ver test_portada_obra.py.
"""

from datetime import date, timedelta
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.agenda.models import Event
from apps.media.models import MediaAsset
from apps.people.models import Contributor
from apps.showcase.models import Partner, PressMention, SiteProfile, SiteSocialLink
from apps.submissions.models import Call
from tests.factories import make_event, make_publication

pytestmark = pytest.mark.django_db


def _imagen(nombre, tamano=(50, 70)):
    buffer = BytesIO()
    Image.new("RGB", tamano, (10, 20, 30)).save(buffer, format="JPEG")
    recurso = MediaAsset(alt_text=nombre)
    recurso.file.save(f"{nombre}.jpg", ContentFile(buffer.getvalue()))
    return recurso


def _portada(client):
    return BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")


def _texto(nodo):
    return " ".join(nodo.get_text().split())


def test_el_nombre_es_el_logo_y_el_lema_baja_a_la_cejilla(client):
    perfil = SiteProfile.load()
    perfil.name = "Repitentes del Verso"
    perfil.tagline = "Colectivo de poesía"
    perfil.location = "Chile"
    perfil.founded_year = 2023
    perfil.save()
    SiteSocialLink.objects.create(
        profile=perfil, platform="Instagram", url="https://www.instagram.com/repitentesdelverso/"
    )
    for i in range(2):
        Contributor.objects.create(slug=f"m{i}", display_name=f"Integrante {i}", is_member=True)
    sopa = _portada(client)
    assert [_texto(h1) for h1 in sopa.select("h1")] == ["Repitentes del Verso"]
    # De .hero-nombre cuelgan la cápsula de la cabecera y cabecera.js.
    assert "hero-nombre" in sopa.h1["class"]
    # Se ve el logo, un dibujo; el nombre va en texto para lectores y buscadores.
    assert sopa.h1.select_one(".sr-only").get_text() == "Repitentes del Verso"
    logos = sopa.h1.select("svg")
    assert [svg["class"] for svg in logos] == [["logo-horizontal"], ["logo-apilado"]]
    assert all(svg["aria-hidden"] == "true" for svg in logos)
    cejilla = sopa.select_one(".hero-cejilla")
    assert cejilla.get_text() == (
        "Colectivo de poesía · Chile · desde 2023 · 2 integrantes · @repitentesdelverso"
    )
    assert cejilla.a["href"] == "https://www.instagram.com/repitentesdelverso/"


@pytest.mark.parametrize(
    ("url", "usuario"),
    [
        ("https://www.instagram.com/repitentesdelverso/", "@repitentesdelverso"),
        ("https://www.instagram.com/repitentesdelverso/reels/", "@repitentesdelverso"),
        ("https://www.instagram.com/", ""),
    ],
)
def test_el_usuario_de_una_red_sale_de_su_url(url, usuario):
    assert SiteSocialLink(platform="Instagram", url=url).usuario == usuario


def test_la_cejilla_cuenta_a_todas(client):
    """Las cuenta todas, también las que esperan su pliego en «El colectivo» (D22)."""
    for i in range(17):
        Contributor.objects.create(slug=f"m{i}", display_name=f"Integrante {i}", is_member=True)
    assert "17 integrantes" in _portada(client).select_one(".hero-cejilla").get_text()


def test_la_hoja_ya_no_lleva_la_cubierta(client):
    """La cubierta acompañaba al nombre; con la obra a sangre arriba ya no va (D18). El libro
    sigue en el bloque de publicaciones."""
    make_publication(slug="primera", title="Cuadernos del ruido", cover=_imagen("cubierta-1"))
    sopa = _portada(client)
    assert sopa.select_one(".hero-objeto, .hero-cubierta") is None
    assert "hero--con-objeto" not in sopa.select_one("section.hero")["class"]
    assert [t.get_text() for t in sopa.select(".home-publicaciones .pub-title")] == [
        "Cuadernos del ruido"
    ]


def test_un_solo_boton_principal_y_el_mismo_correo_que_el_pie(client):
    """El botón principal del titular es el dossier, que la hoja oculta desde donde lo lleva
    la cabecera. «Escríbenos» usa el correo de gestión o, si falta, el general: el del pie."""
    perfil = SiteProfile.load()
    perfil.general_email = "hola@example.com"
    perfil.save()
    sopa = _portada(client)
    principales = sopa.select("section.hero .btn--primary")
    assert len(principales) == 1 and "hero-dossier" in principales[0]["class"]
    assert sopa.select_one("section.hero").find("a", string="Escríbenos")["href"] == (
        "mailto:hola@example.com"
    )
    assert sopa.select_one('footer.site-foot a[href="mailto:hola@example.com"]') is not None


def test_la_portada_no_lleva_cifras(client):
    """El dueño del sitio quitó las cifras (2026-10-14): el colectivo aún es pequeño y
    prefiere no enseñar cuántos son, cuántas actividades y cuántas publicaciones."""
    Contributor.objects.create(slug="m1", display_name="Integrante Uno", is_member=True)
    make_event(
        slug="pasado", type=Event.Type.FESTIVAL, starts_at=timezone.now() - timedelta(days=30)
    )
    make_publication(slug="p", title="P")
    titular = _portada(client).select_one("section.hero")
    assert titular.select_one(".stats-strip, .hero-stats") is None


def test_el_sello_de_la_convocatoria_va_bajo_los_botones(client):
    """Flotaba a la derecha del lema, donde fue después el objeto, y el ticket pedía no taparlo."""
    ahora = timezone.now()
    Call.objects.create(
        slug="abierta",
        title="Convocatoria",
        opens_at=ahora - timedelta(days=1),
        closes_at=ahora + timedelta(days=30),
    )
    texto = _portada(client).select_one(".hero-texto")
    piezas = [hijo["class"][0] for hijo in texto.find_all(recursive=False)]
    assert piezas.index("sello-convocatoria") > piezas.index("hero-ctas")


def test_la_portada_no_lleva_cita_de_prensa_ni_aliados(client):
    """Bajo el titular iba una línea con una cita de prensa y «Con el apoyo de». El dueño del
    sitio la quitó entera (2026-10-14): el colectivo aún es pequeño."""
    PressMention.objects.create(
        title="b",
        outlet="Radio Dos",
        quote="Destacada.",
        featured=True,
        published_on=date(2025, 1, 1),
    )
    Partner.objects.create(name="Casa del Libro")
    sopa = _portada(client)
    assert sopa.select_one(".hero-respaldo, .hero-cita") is None
    assert "Destacada." not in sopa.get_text()
    assert "Casa del Libro" not in sopa.get_text()
