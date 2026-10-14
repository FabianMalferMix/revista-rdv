"""Las imágenes que el modelo ya guarda llegan a los listados (backlog UX, ticket 3.5).

Los textos tenían imagen, los eventos afiche, las fotos crédito y los aliados logo, pero
los listados no enseñaban nada de eso: solo la ficha de cada uno. Aquí se fija dónde
aparece cada pieza y que ninguna cuesta una consulta por fila.
"""

from datetime import timedelta
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.agenda.models import EventPhoto
from apps.content.models import EditorialStatus
from apps.media.models import MediaAsset
from apps.showcase.models import Partner
from tests.factories import make_event

pytestmark = pytest.mark.django_db


def _imagen(nombre, alt="Imagen", credito=""):
    buffer = BytesIO()
    Image.new("RGB", (30, 40), (10, 20, 30)).save(buffer, format="JPEG")
    recurso = MediaAsset(alt_text=alt, credit=credito)
    recurso.file.save(f"{nombre}.jpg", ContentFile(buffer.getvalue()))
    return recurso


def _sopa(client, url):
    return BeautifulSoup(client.get(url).content, "html.parser")


def _texto(make_article, slug, **extra):
    return make_article(
        slug=slug,
        title=f"Texto {slug}",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        **extra,
    )


# ── Textos ────────────────────────────────────────────────────────────────


def test_la_fila_de_un_texto_ensena_su_imagen_a_una_tinta(client, make_article):
    _texto(make_article, "con-imagen", cover_image=_imagen("portada"))
    _texto(make_article, "sin-imagen")
    filas = {
        f.select_one(".fila-titulo").get_text(strip=True): f
        for f in _sopa(client, reverse("content:text_archive")).select("li.fila")
    }
    con = filas["Texto con-imagen"]
    assert "fila--con-miniatura" in con["class"]
    miniatura = con.select_one(".fila-miniatura.riso-duo img")
    assert miniatura is not None, "la fila no enseña la imagen del texto"
    assert miniatura["alt"] == "", "el título ya la nombra"
    assert filas["Texto sin-imagen"].select_one(".fila-miniatura") is None


# ── Afiches ───────────────────────────────────────────────────────────────


def test_la_agenda_ensena_el_afiche_de_cada_actividad(client):
    make_event(slug="con-afiche", title="Con afiche", poster=_imagen("afiche"))
    make_event(slug="sin-afiche", title="Sin afiche")
    tarjetas = _sopa(client, reverse("agenda:agenda")).select("li.event-card")
    afiches = {
        t.select_one("h2").get_text(strip=True): t.select_one(".event-afiche img") for t in tarjetas
    }
    assert afiches["Con afiche"] is not None and afiches["Con afiche"]["alt"] == ""
    assert afiches["Sin afiche"] is None


def test_la_proxima_actividad_de_la_portada_lleva_su_afiche(client):
    make_event(slug="proxima", title="Próxima", poster=_imagen("afiche-proximo"))
    proxima = _sopa(client, reverse("content:home")).select_one(".next-event")
    assert proxima.select_one(".next-event-afiche img") is not None


def test_la_trayectoria_ensena_el_afiche_en_la_fila(client):
    make_event(
        slug="pasada",
        title="Pasada",
        starts_at=timezone.now() - timedelta(days=30),
        poster=_imagen("afiche-pasado"),
    )
    fila = _sopa(client, reverse("agenda:trayectoria")).select_one("li.fila--con-miniatura")
    assert fila is not None and fila.select_one(".fila-miniatura img") is not None


# ── Álbum: crédito y contador ─────────────────────────────────────────────


def test_el_album_dice_de_quien_son_las_fotos_y_cual_es_cual(client):
    evento = make_event(slug="album", title="Álbum", starts_at=timezone.now() - timedelta(days=3))
    for i, credito in enumerate(["Archivo", "Ana Pérez", "Archivo"]):
        EventPhoto.objects.create(
            event=evento,
            asset=_imagen(f"foto-{i}", credito=credito),
            position=i,
            caption=f"Foto {i}",
        )
    sopa = _sopa(client, evento.get_absolute_url())
    assert sopa.select_one(".galeria-creditos").get_text(strip=True) == "Fotos: Ana Pérez · Archivo"
    pies = [" ".join(f.get_text().split()) for f in sopa.select(".lightbox figcaption")]
    assert pies == [
        "1 / 3 · Foto 0 · Archivo",
        "2 / 3 · Foto 1 · Ana Pérez",
        "3 / 3 · Foto 2 · Archivo",
    ]
    assert sopa.select_one(".photo-grid a")["aria-label"] == "Ampliar foto 1 de 3"


def test_sin_credito_no_hay_linea_de_creditos(client):
    evento = make_event(slug="sin-credito", starts_at=timezone.now() - timedelta(days=3))
    EventPhoto.objects.create(event=evento, asset=_imagen("anonima"), position=0)
    sopa = _sopa(client, evento.get_absolute_url())
    assert sopa.select_one(".galeria-creditos") is None
    assert sopa.select_one(".lightbox figcaption").get_text(strip=True) == "1 / 1"


# ── Aliados ───────────────────────────────────────────────────────────────


def test_los_aliados_van_por_tipo_en_el_orden_de_los_tipos(client):
    """Un fondo y una sala no son lo mismo para quien programa."""
    for nombre, tipo in (
        ("Sala Uno", Partner.Kind.ESPACIO),
        ("Fondo Uno", Partner.Kind.FINANCIAMIENTO),
        ("Editorial Uno", Partner.Kind.EDITORIAL),
    ):
        Partner.objects.create(name=nombre, kind=tipo, logo=_imagen(f"logo-{tipo}"))
    sopa = _sopa(client, reverse("showcase:partner_index"))
    grupos = [g.select_one("h2").get_text(strip=True) for g in sopa.select(".aliados-grupo")]
    assert grupos == ["Financiamiento", "Editoriales", "Espacios"]
    assert len(sopa.select(".aliados-grupo .partner-logo")) == 3


def test_un_aliado_sin_logo_lleva_su_nombre_en_la_caja_del_logo(client):
    """En /aliados/ la caja quedaba vacía y el nombre arrancaba donde los demás tienen el
    logo. Allí el nombre ya va escrito al lado: la caja no se lee dos veces. En el dossier
    el nombre va solo en la caja, sin el pie que llevan los logos."""
    Partner.objects.create(name="Fondo Sin Logo", kind=Partner.Kind.FINANCIAMIENTO)
    Partner.objects.create(name="Fondo Con Logo", logo=_imagen("logo-con"))
    caja = _sopa(client, reverse("showcase:partner_index")).select_one(".partner-logo--texto")
    assert caja.get_text() == "Fondo Sin Logo" and caja["aria-hidden"] == "true"
    aliados = _sopa(client, reverse("showcase:dossier")).select(".dossier-aliados li")
    textos = {li.get_text(" ", strip=True): li for li in aliados}
    assert set(textos) == {"Fondo Sin Logo", "Fondo Con Logo"}
    sin_logo = textos["Fondo Sin Logo"].select_one(".partner-logo--texto")
    assert sin_logo is not None and not sin_logo.has_attr("aria-hidden")


# ── Ninguna imagen cuesta una consulta por fila ───────────────────────────


@pytest.mark.parametrize(
    "vista,crear",
    [
        ("content:text_archive", "textos"),
        ("agenda:agenda", "proximas"),
        ("agenda:trayectoria", "pasadas"),
    ],
)
def test_las_imagenes_de_los_listados_no_cuestan_una_consulta_por_fila(
    client, make_article, vista, crear
):
    def sembrar(desde, hasta):
        for i in range(desde, hasta):
            if crear == "textos":
                _texto(make_article, f"t{i}", cover_image=_imagen(f"t{i}"))
            else:
                dias = timedelta(days=i + 1)
                make_event(
                    slug=f"e{i}",
                    starts_at=timezone.now() + (dias if crear == "proximas" else -dias),
                    poster=_imagen(f"e{i}"),
                )

    def consultas():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(reverse(vista)).status_code == 200
        return len(ctx)

    sembrar(0, 2)
    # La primera petición crea el perfil del sitio (SiteProfile.load): se descuenta.
    client.get(reverse(vista))
    con_dos = consultas()
    sembrar(2, 6)
    assert consultas() == con_dos, "cada imagen de la lista añade una consulta"
