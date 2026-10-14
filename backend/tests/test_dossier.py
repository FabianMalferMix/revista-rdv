from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Event, Milestone
from apps.agenda.services import cronologia
from apps.content.models import EditorialStatus
from apps.people.models import Contributor
from apps.reviews.models import Publisher
from apps.showcase.models import Partner, PressMention, Publication, SiteProfile, SiteSocialLink
from tests.factories import make_event, make_image, make_publication

pytestmark = pytest.mark.django_db

SANTIAGO = ZoneInfo("America/Santiago")


@pytest.fixture
def profile(db):
    p = SiteProfile.load()
    p.name = "Colectivo Prueba"
    p.tagline = "Poesía que camina."
    p.manifesto = "Somos un colectivo dedicado a la palabra."
    p.booking_email = "gestion@example.com"
    p.founded_year = 2019
    p.save()
    return p


def test_dossier_aggregates_everything(client, profile):
    Contributor.objects.create(
        slug="poeta-dossier",
        display_name="Poeta Dossier",
        is_member=True,
        short_bio="Escribe y gestiona.",
    )
    Publication.objects.create(
        slug="pub-dossier", title="Plaquette Dossier", published=True, year=2022
    )
    PressMention.objects.create(title="n", outlet="Medio Dossier", quote="Notables.")
    Partner.objects.create(name="Fondo Dossier")

    resp = client.get(reverse("showcase:dossier"))
    assert resp.status_code == 200
    for fragment in [
        b"Colectivo Prueba",
        b"Somos un colectivo dedicado a la palabra.",
        b"Poeta Dossier",
        b"Plaquette Dossier",
        b"Notables.",
        b"Fondo Dossier",
        b"gestion@example.com",
        b"data-print",  # botón de impresión (el handler vive en dossier.js, sin inline)
    ]:
        assert fragment in resp.content

    # El botón de imprimir ya no usa handler inline (incompatible con la CSP).
    assert b"onclick" not in resp.content
    assert b"js/dossier.js" in resp.content


def test_dossier_excludes_unpublished_publication(client, profile):
    Publication.objects.create(slug="oculta-d", title="Oculta Dossier", published=False)
    resp = client.get(reverse("showcase:dossier"))
    assert b"Oculta Dossier" not in resp.content


def test_home_cta_links_to_dossier_page_without_pdf(client, profile):
    """Sin PDF el botón abre la página del dossier, y lo dice: «Ver», no «Descargar»."""
    resp = client.get(reverse("content:home"))
    assert b"Ver el dossier" in resp.content
    assert b"Descargar dossier" not in resp.content, "promete una descarga que no ocurre"
    assert reverse("showcase:dossier").encode() in resp.content
    # «Escríbenos» (ticket 4.2), con el correo de gestión: el mismo que el pie.
    assert b'href="mailto:gestion@example.com">Escr\xc3\xadbenos' in resp.content


def test_home_cta_descarga_el_pdf_cuando_existe(client, profile):
    """Con PDF maquetado el botón sí descarga, y enlaza al archivo."""
    profile.dossier_pdf.name = "dossier/kit-de-prensa.pdf"
    profile.save()
    html = client.get(reverse("content:home")).content.decode()
    assert "Descargar dossier (PDF)" in html
    assert "kit-de-prensa.pdf" in html
    assert "Ver el dossier" not in html


def test_home_cta_prefers_uploaded_pdf(client, profile):
    profile.dossier_pdf = SimpleUploadedFile("dossier.pdf", b"%PDF-1.4 fake")
    profile.save()
    resp = client.get(reverse("content:home"))
    assert profile.dossier_pdf.url.encode() in resp.content


def test_dossier_page_offers_pdf_download_when_uploaded(client, profile):
    profile.dossier_pdf = SimpleUploadedFile("dossier2.pdf", b"%PDF-1.4 fake")
    profile.save()
    resp = client.get(reverse("showcase:dossier"))
    assert b"Descargar PDF maquetado" in resp.content


# ── El dossier como kit de prensa (ticket 5.1) ────────────────────────────


def _sopa(client):
    return BeautifulSoup(client.get(reverse("showcase:dossier")).content, "html.parser")


def test_el_titulo_dice_que_es_el_dossier(client, profile):
    """La barra, el pie y el botón de la cabecera llaman a la página «Dossier», y su título
    era solo el nombre del colectivo. El botón de imprimir iba antes que el título."""
    cabeza = _sopa(client).select_one(".dossier-head")
    assert cabeza.select_one(".kicker").get_text() == "Dossier · kit de prensa"
    assert cabeza.h1.get_text() == "Colectivo Prueba"
    assert [e.name for e in cabeza.find_all(["h1", "button"])] == ["h1", "button"]


def test_el_boton_de_imprimir_solo_aparece_con_javascript(client, profile):
    """Sin JavaScript no haría nada: llega oculto, y dossier.js lo enseña al enlazarlo."""
    assert _sopa(client).select_one("button[data-print]").has_attr("hidden")
    js = (settings.BASE_DIR / "static" / "js" / "dossier.js").read_text(encoding="utf-8")
    assert "btn.hidden = false" in js


def test_la_trayectoria_es_una_sola_y_va_de_lo_mas_reciente_a_lo_mas_antiguo(client, profile):
    """Eran dos listas seguidas, primero los hitos y después los eventos, y los años salían
    desordenados (2022, 2019, 2026, 2025). Ahora es una, por años, con los hitos, las
    publicaciones y los eventos de cada uno. Una publicación sin año no tiene dónde ir."""
    Milestone.objects.create(year=2019, title="Fundación")
    Milestone.objects.create(year=2022, title="Primera plaquette")
    make_publication(slug="libro", title="Un libro", year=2024)
    make_publication(slug="sin-anio", title="Sin año", year=None)
    make_event(
        slug="recital", title="Recital", starts_at=datetime(2026, 1, 15, 20, tzinfo=SANTIAGO)
    )
    make_event(
        slug="festival",
        title="Festival",
        type=Event.Type.FESTIVAL,
        starts_at=datetime(2025, 9, 30, 20, tzinfo=SANTIAGO),
        is_external=True,
        host="Festival de Poesía Joven",
        city="Valparaíso",
    )
    sopa = _sopa(client)
    anios = [int(h3.get_text()) for h3 in sopa.select(".cronologia-anio > h3")]
    assert anios == [2026, 2025, 2024, 2022, 2019]
    filas = {
        li.select_one(".cronologia-titulo").get_text(strip=True): li
        for li in sopa.select(".cronologia-filas > li")
    }
    assert set(filas) == {"Recital", "Festival", "Un libro", "Primera plaquette", "Fundación"}
    festival = filas["Festival"]
    assert festival.select_one(".rotulo").get_text() == "Festival"
    assert festival.select_one(".meta").get_text() == "Festival de Poesía Joven · Valparaíso"
    assert filas["Un libro"].select_one(".rotulo").get_text() == "Plaquette"
    assert filas["Fundación"].select_one(".rotulo").get_text() == "Hito"
    assert filas["Fundación"].a is None, "un hito no lleva a ninguna parte"
    assert "Sin año" in sopa.select_one(".dossier-publicaciones").get_text()


def test_el_anio_de_un_evento_es_el_de_su_hora_local(client):
    """Un recital del 31 de diciembre a las 22:00 en Santiago ya es 1 de enero en UTC: va
    en el año que termina, el que enseña su fecha, y su ficha lleva a ese año."""
    noche = datetime(2025, 12, 31, 22, tzinfo=SANTIAGO)
    evento = make_event(slug="fin-de-anio", title="Fin de año", starts_at=noche)
    # Leído de la base, como en la página, viene en UTC: ahí ya es el año siguiente.
    evento = Event.objects.get(pk=evento.pk)
    assert evento.starts_at.year == 2026
    assert [bloque["year"] for bloque in cronologia([evento])] == [2025]
    assert "#anio-2025" in client.get(evento.get_absolute_url()).content.decode()


def test_la_ficha_reune_los_datos_del_colectivo(client, profile, make_article):
    """Fundado, lugar, contacto, Instagram, sitio y la fecha de la última publicación: lo
    que un programador copia en su ficha. El correo es el mismo del pie y de la portada."""
    profile.location = "Valparaíso"
    profile.save()
    SiteSocialLink.objects.create(
        profile=profile, platform="Instagram", url="https://www.instagram.com/colectivo.prueba/"
    )
    make_article(
        status=EditorialStatus.PUBLISHED, published_at=datetime(2026, 3, 5, 12, tzinfo=SANTIAGO)
    )
    sopa = _sopa(client)
    datos = {
        div.dt.get_text(): div.dd for div in sopa.select(".dossier-ficha .dossier-datos > div")
    }
    assert list(datos) == ["Fundado", "Lugar", "Contacto", "Instagram", "Sitio", "Actualizado"]
    assert datos["Fundado"].get_text() == "2019"
    assert datos["Lugar"].get_text() == "Valparaíso"
    assert datos["Contacto"].a["href"] == "mailto:gestion@example.com"
    assert datos["Instagram"].a.get_text() == "@colectivo.prueba"
    assert datos["Sitio"].get_text() == "testserver"
    assert datos["Actualizado"].get_text() == "el 5 de marzo de 2026"
    contacto = sopa.select_one("#contacto")
    assert contacto.select_one('a[href="mailto:gestion@example.com"]') is not None
    assert contacto.select_one('a[href="https://www.instagram.com/colectivo.prueba/"]') is not None


def test_las_cifras_nombran_integrantes_y_festivales(client, profile):
    """D11: las cifras que busca un jurado, con el nombre de cada una. Sin ferias, la de
    ferias no aparece: un cero no dice nada."""
    for n in range(3):
        Contributor.objects.create(slug=f"i{n}", display_name=f"Integrante {n}", is_member=True)
    make_event(
        slug="fest", type=Event.Type.FESTIVAL, starts_at=datetime(2025, 9, 30, 20, tzinfo=SANTIAGO)
    )
    cifras = {" ".join(li.get_text().split()) for li in _sopa(client).select(".dossier-cifras li")}
    assert {"3 integrantes", "1 actividad", "1 festival"} <= cifras
    assert not [c for c in cifras if "feria" in c]


def test_retratos_cubiertas_y_logos_salen_al_imprimir(client, profile):
    """Una imagen diferida que el navegador aún no ha pedido sale en blanco al imprimir: las
    del dossier se piden con la página. Cada una acompaña a un nombre ya escrito, así que
    un lector de pantalla no la lee."""
    Contributor.objects.create(
        slug="con-foto", display_name="Con Foto", is_member=True, photo=make_image("retrato")
    )
    make_publication(slug="con-cubierta", title="Con cubierta", cover=make_image("cubierta"))
    Partner.objects.create(name="Con logo", logo=make_image("logo"))
    sopa = _sopa(client)
    for selector in (".dossier-integrante img", ".dossier-publicacion img", ".dossier-aliados img"):
        imagen = sopa.select_one(selector)
        assert imagen is not None, f"falta {selector}"
        assert not imagen.has_attr("loading"), f"{selector} espera a que se baje hasta ella"
        assert imagen["alt"] == ""


def test_el_dossier_cuesta_lo_mismo_con_una_pieza_que_con_muchas(client, profile):
    """Retratos, cubiertas, editoriales y logos vienen en la consulta de su lista: con
    cuatro integrantes, publicaciones, aliados, hitos, eventos y citas, las mismas
    consultas que con una de cada."""

    def sembrar(n):
        Contributor.objects.create(
            slug=f"m{n}", display_name=f"Integrante {n}", is_member=True, photo=make_image(f"r{n}")
        )
        editorial = Publisher.objects.create(slug=f"ed{n}", name=f"Editorial {n}")
        make_publication(
            slug=f"p{n}", title=f"Pub {n}", cover=make_image(f"c{n}"), publisher=editorial
        )
        Partner.objects.create(name=f"Aliado {n}", logo=make_image(f"l{n}"))
        Milestone.objects.create(year=2020 + n, title=f"Hito {n}")
        make_event(slug=f"e{n}", starts_at=timezone.now() - timedelta(days=10 + n))
        PressMention.objects.create(title="t", outlet=f"Medio {n}", quote="Cita.")

    url = reverse("showcase:dossier")
    sembrar(0)
    client.get(url)  # en caliente: el perfil ya existe
    with CaptureQueriesContext(connection) as una:
        client.get(url)
    for n in (1, 2, 3):
        sembrar(n)
    with CaptureQueriesContext(connection) as cuatro:
        client.get(url)
    assert len(cuatro) == len(una), "una consulta más por pieza"
