"""La portada completa.

Después de la hoja, la portada ordena sus bloques: el destacado (la tirada de registros o el
poema destacado), la próxima actividad, la obra (los últimos poemas con sus tres primeros
versos, junto a los últimos textos), «Las voces», las publicaciones y un cierre para
programadores y jurados. Cada sección lleva encima su parte del sitio y, bajo el título, el
filete de su territorio.
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
from apps.media.models import MediaAsset, Recording
from apps.people.models import Contributor
from apps.showcase.models import SiteProfile
from apps.site.services import ultima_publicacion
from tests import css
from tests.factories import (
    make_article,
    make_event,
    make_poem,
    make_publication,
    make_published_article,
    soup,
)

pytestmark = pytest.mark.django_db

PUBLICADO = EditorialStatus.PUBLISHED


def _portada(client):
    return soup(client, reverse("site:home"))


def _cubierta(nombre):
    buffer = BytesIO()
    Image.new("RGB", (50, 70), (10, 20, 30)).save(buffer, format="JPEG")
    recurso = MediaAsset(alt_text=nombre)
    recurso.file.save(f"{nombre}.jpg", ContentFile(buffer.getvalue()))
    return recurso


def _featured_excerpt(client, body):
    profile = SiteProfile.load()
    profile.featured_poem = make_poem(
        slug="p-dest",
        title="Poema Destacado",
        body=body,
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    profile.save()
    sopa = BeautifulSoup(client.get(reverse("site:home")).content, "html.parser")
    assert sopa.select_one(".tirada") is None
    return sopa.select_one(".featured .poem-excerpt")


def test_featured_poem_excerpt_keeps_its_verses_and_stanzas(client):
    """Sin registros destacados, la portada cita el poema verso a verso, con su sangría y
    sus estrofas enteras: la tercera no cabe en los seis versos y no se parte."""
    extracto = _featured_excerpt(
        client, "Uno\ndos\n\n    tres\n    cuatro\n    cinco\n\nseis\nsiete"
    )
    versos = [v.get_text() for v in extracto.select(".estrofa > .verso")]
    assert versos == ["Uno", "dos", "    tres", "    cuatro", "    cinco"]
    assert len(extracto.select(".estrofa")) == 2
    assert "seis" not in extracto.get_text()


def test_featured_prose_poem_is_cut_at_a_word(client):
    extracto = _featured_excerpt(client, "palabra " * 100)
    (verso,) = extracto.select(".verso")
    assert verso.get_text().endswith("palabra…")
    assert len(verso.get_text()) <= 281


def test_featured_poem_long_first_stanza_stops_at_six_verses(client):
    cuerpo = "\n".join(f"verso {n}" for n in range(1, 10))
    extracto = _featured_excerpt(client, cuerpo)
    assert [v.get_text() for v in extracto.select(".verso")] == [f"verso {n}" for n in range(1, 7)]


def test_los_poemas_se_leen_por_sus_tres_primeros_versos(client):
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


def test_home_shows_next_event(client):
    make_event(slug="siguiente", title="Actividad Siguiente")
    make_event(slug="hecho", title="Hecho", starts_at=timezone.now() - timedelta(days=5))
    resp = client.get(reverse("site:home"))
    assert b"Actividad Siguiente" in resp.content


def test_home_caps_articles_and_links_to_archive(client):
    for i in range(8):
        make_published_article(slug=f"t{i}", title=f"Texto {i}")
    resp = client.get(reverse("site:home"))
    assert resp.status_code == 200
    # Portada curada: los tres últimos textos. El resto vive en el archivo, a un enlace.
    sopa = BeautifulSoup(resp.content, "html.parser")
    assert len(sopa.select(".home-obra li.article-card:not(.fila--poema)")) == 3
    assert sopa.select_one(f'.home-obra a[href="{reverse("content:text_archive")}"]') is not None


def test_el_orden_de_los_bloques(client):
    """La obra va antes que las integrantes; después, las publicaciones, y el cierre, al
    final."""
    Contributor.objects.create(slug="m1", display_name="Integrante Uno", is_member=True)
    make_poem(status=PUBLICADO, published_at=timezone.now())
    make_article(status=PUBLICADO, published_at=timezone.now())
    make_publication(slug="uno", title="Uno")
    make_publication(slug="dos", title="Dos")
    secciones = [
        clase
        for seccion in _portada(client).select("main section")
        for clase in seccion["class"]
        if clase.startswith("home-") and clase != "home-block"
    ]
    assert secciones == ["home-obra", "home-integrantes", "home-publicaciones", "home-cierre"]


def test_cada_seccion_lleva_su_cejilla_y_su_territorio(client):
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
        # El título va sin cifra: cuántas son lo dice la cejilla de la hoja.
        "Las voces": ("colectivo", "El colectivo"),
        "Poemas": ("obra", None),
        "Textos": ("obra", None),
        "Para programadores y jurados": ("prensa", "Prensa y gestión"),
    }
    # La obra lleva su cejilla una vez, sobre las dos columnas.
    assert sopa.select_one(".home-obra-cejilla").get_text() == "La obra"


def test_las_publicaciones_las_ensena_todas(client):
    """Arriba no va ningún libro: el bloque de publicaciones los enseña todos, también los que
    tienen cubierta."""
    make_publication(slug="primera", title="Primera", position=0, cover=_cubierta("c1"))
    make_publication(slug="segunda", title="Segunda", position=1, cover=_cubierta("c2"))
    make_publication(slug="tercera", title="Tercera", position=2)
    titulos = [t.get_text() for t in _portada(client).select(".home-publicaciones .estante-titulo")]
    assert titulos == ["Primera", "Segunda", "Tercera"]


def test_con_un_solo_libro_hay_bloque_de_publicaciones(client):
    make_publication(slug="unica", title="Única", cover=_cubierta("c1"))
    assert _portada(client).select_one(".home-publicaciones") is not None


def test_el_cierre_lleva_sus_puertas_la_ultima_actividad_y_la_fecha(client):
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


def test_la_ultima_publicacion_solo_cuenta_lo_publicado():
    """Un borrador o un registro sin publicar no hacen más reciente la portada."""
    assert ultima_publicacion() is None
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
    assert ultima_publicacion() == ahora - timedelta(days=10)


def test_las_puertas_del_cierre_son_sellos_en_risografia():
    """Cada puerta de «Prensa y gestión» es un sello con grano y una segunda tinta corrida que
    no calza; las palabras pequeñas, sin ella, para que se lean. Se endereza al señalarlo solo
    si no se pidió menos movimiento (ver «“Prensa y gestión”, sellos en risografía» en
    docs/deferidos-y-decisiones.md)."""
    assert "feTurbulence" in css.tokens()["--grano"]
    assert css.rule((), ".home-cierre .pie-entidad li")["mask-image"] == "var(--grano)"
    pasada = css.rule((), ".home-cierre .pie-entidad li::before")
    for propiedad, valor in (
        ("content", '""'),
        ("position", "absolute"),
        ("translate", "4px 3px"),
        ("mix-blend-mode", "multiply"),
    ):
        assert pasada.get(propiedad) == valor, propiedad
    palabra = css.rule((), ".home-cierre .pie-entidad a")
    assert palabra["text-shadow"] == "3px 2px 0 color-mix(in srgb, var(--otra) 85%, transparent)"
    movimiento = ("@media (prefers-reduced-motion:no-preference)",)
    enderezado = ".home-cierre .pie-entidad li:is(:hover, :focus-within)"
    assert css.rule(movimiento, enderezado)["rotate"] == "0deg"
    assert {r.context for r in css.rules() if r.selector == enderezado} == {movimiento}
