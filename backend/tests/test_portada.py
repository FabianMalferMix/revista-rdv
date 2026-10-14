"""La portada completa (backlog UX, ticket 4.3; D13).

Después del titular, la portada ordena sus bloques: el destacado, las integrantes («12
voces»), la obra (los últimos poemas con sus tres primeros versos, junto a los últimos
textos), las publicaciones que el titular no enseña ya y un cierre para programadores y
jurados. Cada sección lleva encima su parte del sitio y, bajo el título, el filete de su
territorio. El dueño del sitio eligió conservar el bloque de publicaciones.
"""

from datetime import timedelta
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.content.models import EditorialStatus
from apps.content.views import _ultima_publicacion
from apps.media.models import MediaAsset, Recording
from apps.people.models import Contributor
from apps.showcase.models import SiteProfile
from tests.factories import make_event, make_publication

pytestmark = pytest.mark.django_db

PUBLICADO = EditorialStatus.PUBLISHED


def _portada(client):
    return BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")


def _cubierta(nombre):
    buffer = BytesIO()
    Image.new("RGB", (50, 70), (10, 20, 30)).save(buffer, format="JPEG")
    recurso = MediaAsset(alt_text=nombre)
    recurso.file.save(f"{nombre}.jpg", ContentFile(buffer.getvalue()))
    return recurso


def test_los_poemas_se_leen_por_sus_tres_primeros_versos(client, make_poem):
    """Los tres últimos, cada uno con sus tres primeros versos: sin las líneas en blanco y
    sin la sangría, que en una cita no se compone."""
    ahora = timezone.now()
    for dias, titulo in ((4, "El más viejo"), (3, "Tercero"), (2, "Segundo"), (1, "Primero")):
        make_poem(
            title=titulo,
            status=PUBLICADO,
            published_at=ahora - timedelta(days=dias),
            body="\nUno\n    dos, con sangría\n\ntres\ncuatro",
        )
    filas = _portada(client).select(".home-obra .fila--poema")
    assert [f.h3.get_text(strip=True) for f in filas] == ["Primero", "Segundo", "Tercero"]
    assert [v.get_text() for v in filas[0].select(".fila-versos span")] == [
        "Uno",
        "dos, con sangría",
        "tres",
    ]


def test_el_orden_de_los_bloques(client, make_poem, make_article):
    """Las integrantes van antes que la obra: son lo que buscan los programadores. El
    cierre, al final."""
    Contributor.objects.create(slug="m1", display_name="Integrante Uno", is_member=True)
    make_poem(status=PUBLICADO, published_at=timezone.now())
    make_article(status=PUBLICADO, published_at=timezone.now())
    make_publication(slug="uno", title="Uno")
    make_publication(slug="dos", title="Dos")
    secciones = [
        clase
        for seccion in _portada(client).select("main > section")
        for clase in seccion["class"]
        if clase.startswith("home-") and clase != "home-block"
    ]
    assert secciones == ["home-integrantes", "home-obra", "home-publicaciones", "home-cierre"]


def test_cada_seccion_lleva_su_cejilla_y_su_territorio(client, make_poem, make_article):
    for i in range(3):
        Contributor.objects.create(slug=f"m{i}", display_name=f"Integrante {i}", is_member=True)
    make_poem(status=PUBLICADO, published_at=timezone.now())
    make_article(status=PUBLICADO, published_at=timezone.now())
    sopa = _portada(client)
    cabezas = {
        cabeza.h2.get_text(): (
            cabeza.get("data-territorio"),
            cabeza.p.get_text() if cabeza.p else None,
        )
        for cabeza in sopa.select(".seccion-cabeza")
    }
    assert cabezas == {
        "3 voces": ("colectivo", "El colectivo"),
        "Poemas": ("obra", None),
        "Textos": ("obra", None),
        "Para programadores y jurados": ("prensa", "Prensa y gestión"),
    }
    # La obra lleva su cejilla una vez, sobre las dos columnas.
    assert sopa.select_one(".home-obra-cejilla").get_text() == "La obra"
    # Sin `only` en el include, una sección sin cejilla pintaba la lista del titular.
    assert not [r for r in sopa.select("main .rotulo") if r.get_text().startswith("[")]


def test_las_publicaciones_no_repiten_el_libro_del_titular(client):
    make_publication(slug="primera", title="Primera", position=0, cover=_cubierta("c1"))
    make_publication(slug="segunda", title="Segunda", position=1, cover=_cubierta("c2"))
    make_publication(slug="tercera", title="Tercera", position=2)
    sopa = _portada(client)
    assert sopa.select_one(".hero-objeto a")["href"] == reverse(
        "showcase:publication_detail", args=["primera"]
    )
    titulos = [t.get_text() for t in sopa.select(".home-publicaciones .pub-title")]
    assert titulos == ["Segunda", "Tercera"]


def test_si_solo_hay_el_libro_del_titular_no_hay_bloque_de_publicaciones(client):
    make_publication(slug="unica", title="Única", cover=_cubierta("c1"))
    sopa = _portada(client)
    assert sopa.select_one(".hero-objeto") is not None
    assert sopa.select_one(".home-publicaciones") is None


def test_el_cierre_lleva_sus_puertas_la_ultima_actividad_y_la_fecha(client, make_article):
    perfil = SiteProfile.load()
    perfil.general_email = "hola@example.com"
    perfil.save()
    ahora = timezone.now()
    make_event(slug="vieja", title="Lectura vieja", starts_at=ahora - timedelta(days=60))
    make_event(slug="reciente", title="Recital reciente", starts_at=ahora - timedelta(days=5))
    make_event(slug="futura", title="Recital futuro", starts_at=ahora + timedelta(days=5))
    make_article(status=PUBLICADO, published_at=ahora - timedelta(days=30))
    Recording.objects.create(
        slug="r",
        title="Registro",
        embed_url="https://youtu.be/xyz123ab",
        published=True,
        published_at=ahora - timedelta(days=2),
    )
    cierre = _portada(client).select_one(".home-cierre")
    puertas = {a.get_text(): a["href"] for a in cierre.select(".pie-entidad a")}
    assert puertas == {
        "Dossier": reverse("showcase:dossier"),
        "Prensa": reverse("showcase:press_index"),
        "Aliados": reverse("showcase:partner_index"),
        "Escríbenos": "mailto:hola@example.com",
    }
    datos = cierre.select_one(".home-cierre-datos")
    assert datos.a["href"] == reverse("agenda:event_detail", args=["reciente"])
    hace_dos_dias = timezone.localtime(ahora - timedelta(days=2))
    assert f"Actualizado el {hace_dos_dias.day} de " in datos.get_text()


def test_sin_correo_el_cierre_lleva_tres_puertas(client):
    puertas = [a.get_text() for a in _portada(client).select(".home-cierre .pie-entidad a")]
    assert puertas == ["Dossier", "Prensa", "Aliados"]


def test_la_ultima_publicacion_solo_cuenta_lo_publicado(make_poem, make_article):
    """Un borrador o un registro sin publicar no hacen más reciente la portada."""
    assert _ultima_publicacion() is None
    ahora = timezone.now()
    make_poem(status=PUBLICADO, published_at=ahora - timedelta(days=10))
    make_article(status=EditorialStatus.DRAFT, published_at=ahora - timedelta(days=1))
    Recording.objects.create(
        slug="borrador",
        title="Sin publicar",
        embed_url="https://youtu.be/xyz123ab",
        published=False,
        published_at=ahora,
    )
    assert _ultima_publicacion() == ahora - timedelta(days=10)
