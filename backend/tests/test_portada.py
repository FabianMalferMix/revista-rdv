"""La portada completa (backlog UX, ticket 4.3; D13).

Después del titular, la portada ordena sus bloques: el destacado, la obra (los últimos
poemas con sus tres primeros versos, junto a los últimos textos), las integrantes («12
voces»), las publicaciones y un cierre para programadores y jurados. Cada sección lleva encima su parte del sitio y, bajo el título, el filete de su
territorio. El dueño del sitio eligió conservar el bloque de publicaciones.
"""

from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.content.models import EditorialStatus
from apps.content.services import ultima_publicacion
from apps.content.templatetags.versos import primera_pausa
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
    """La obra, las integrantes, las publicaciones y el cierre. La obra va primero porque
    lo pidió el dueño del sitio al ver la portada; el cierre, al final."""
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
        # Sin cifra desde D22: «3 voces» decía el tamaño del colectivo.
        "Las voces": ("colectivo", "El colectivo"),
        "Poemas": ("obra", None),
        "Textos": ("obra", None),
        "Para programadores y jurados": ("prensa", "Prensa y gestión"),
    }
    # La obra lleva su cejilla una vez, sobre las dos columnas.
    assert sopa.select_one(".home-obra-cejilla").get_text() == "La obra"
    # Sin `only` en el include, una sección sin cejilla pintaba la lista del titular.
    assert not [r for r in sopa.select("main .rotulo") if r.get_text().startswith("[")]


def test_las_publicaciones_las_ensena_todas(client):
    """El titular se quedaba con el primer libro con cubierta y el bloque no lo repetía. Con
    la portada como obra (D18) ya no hay libro arriba: el bloque los enseña todos."""
    make_publication(slug="primera", title="Primera", position=0, cover=_cubierta("c1"))
    make_publication(slug="segunda", title="Segunda", position=1, cover=_cubierta("c2"))
    make_publication(slug="tercera", title="Tercera", position=2)
    titulos = [t.get_text() for t in _portada(client).select(".home-publicaciones .estante-titulo")]
    assert titulos == ["Primera", "Segunda", "Tercera"]


def test_con_un_solo_libro_hay_bloque_de_publicaciones(client):
    make_publication(slug="unica", title="Única", cover=_cubierta("c1"))
    assert _portada(client).select_one(".home-publicaciones") is not None


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
    """D31: cada puerta de «Prensa y gestión» es un sello con grano y una segunda tinta corrida
    que no calza; las palabras pequeñas, sin ella, para que se lean. Se endereza al señalarlo
    solo si no se pidió menos movimiento."""
    css = (Path(__file__).resolve().parent.parent / "static" / "css" / "site.css").read_text()
    assert "feTurbulence" in css and "mask-image:var(--grano)" in css
    assert '.home-cierre .pie-entidad li::before{content:""; position:absolute;' in css
    assert "translate:4px 3px; mix-blend-mode:multiply}" in css
    assert "text-shadow:3px 2px 0 color-mix(in srgb, var(--otra) 85%, transparent)" in css
    movimiento = css[css.index("@media (prefers-reduced-motion:no-preference){\n  .home-cierre") :]
    assert ".home-cierre .pie-entidad li:is(:hover, :focus-within){rotate:0deg" in movimiento


def test_la_hoja_es_una_lamina_a_dos_tintas():
    """D33: desde 900 px, el manifiesto en letra de cartel y tinta azul con grano a la
    izquierda, y a la derecha un círculo de trama magenta con el sello de la convocatoria
    encima. El grano es uno solo para toda la portada, y no se come el foco."""
    css = (Path(__file__).resolve().parent.parent / "static" / "css" / "site.css").read_text()
    raiz = css[: css.index("}")]
    assert "--grano:url(" in raiz and css.count("--grano:url(") == 1
    lamina = css[css.index("/* La hoja como lámina a dos tintas (D33)") :]
    lamina = lamina[: lamina.index("\n}\n")]
    assert "@media (min-width:900px){" in lamina
    assert ".hero{grid-template-columns:minmax(0,7fr) minmax(0,5fr);" in lamina
    # Letra de cartel: el azul sobre el papel solo cumple AA en letra grande.
    assert "font-weight:700; font-size:var(--t5);" in lamina
    assert "@media (min-width:1600px){\n  .hero-manifesto{font-size:var(--t6)}" in css
    assert "color:var(--caratula)" in lamina and "mask-image:var(--grano)" in lamina
    assert ".hero-manifesto:has(:focus-visible){-webkit-mask-image:none; mask-image:none}" in lamina
    assert "radial-gradient(circle, var(--accent) 0 32%, transparent 36%) 0 0 / 13px 13px" in lamina
    assert ".sello-convocatoria{grid-column:2; grid-row:1 / span 3;" in lamina


def test_el_manifiesto_termina_en_su_primera_pausa(client):
    """D33: la portada cita el manifiesto hasta su primera pausa, no a media frase."""
    perfil = SiteProfile.load()
    perfil.manifesto = (
        "Somos un colectivo que lee en voz alta y lleva los poemas a donde no suelen llegar: "
        "salas de clases, ferias y plazas. Lo demás vuelve al taller."
    )
    perfil.save()
    manifiesto = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    texto = " ".join(manifiesto.select_one(".hero-manifesto").get_text().split())
    assert texto == (
        "Somos un colectivo que lee en voz alta y lleva los poemas a donde no suelen llegar. "
        "Conócenos →"
    )


LARGA = " ".join(f"palabra{n}" for n in range(1, 41)) + "."


@pytest.mark.parametrize(
    "texto,cita",
    [
        ("Leemos en voz alta. Escribimos juntas.", "Leemos en voz alta."),
        ("Leemos en voz alta; escribimos juntas.", "Leemos en voz alta."),
        ("¿Quién lee en voz alta? Nosotras.", "¿Quién lee en voz alta?"),
        ("Somos 2.000 lectores: y más", "Somos 2.000 lectores."),
        ("  Sin  pausa  ninguna  ", "Sin pausa ninguna"),
        (LARGA, " ".join(LARGA.split()[:28]) + " …"),
        ("", ""),
        (None, ""),
    ],
)
def test_primera_pausa(texto, cita):
    """Hasta el primer punto, dos puntos, punto y coma, cierre de pregunta o de exclamación
    (los dos puntos y el punto y coma, cerrados con punto); un punto dentro de una cifra no
    es una pausa. Si la pausa llega tarde, la palabra 28, como antes."""
    assert primera_pausa(texto) == cita
