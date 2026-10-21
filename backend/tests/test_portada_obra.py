"""La portada como obra (D18): la mancheta de afiche con telón que eligió el dueño del sitio
en el tablero de la portada (2026-10-20).

La primera vista es una obra a sangre con el logo al pie; lo que era el titular pasa a la
hoja que sigue. La obra la elige el colectivo en el perfil del sitio y sale en AVIF y WebP,
con un recorte vertical para el teléfono; sin ella, va la lámina del estreno. El alto, el
asomo y el telón están en test_css_sistema.py; la hoja, en test_titular.py.
"""

from io import BytesIO
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.media.models import MediaAsset
from apps.media.templatetags.images import LAMINA, PORTADA_TELEFONO
from apps.showcase.admin import SiteProfileAdmin
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db

ESTATICOS = Path(__file__).resolve().parent.parent / "static" / "img" / "portada"


def _recurso(nombre="obra.jpg", tamano=(1500, 900), alt="Lectura en la plaza"):
    buffer = BytesIO()
    Image.new("RGB", tamano, (200, 60, 120)).save(buffer, format="JPEG")
    recurso = MediaAsset.objects.create(
        file=SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/jpeg"),
        alt_text=alt,
    )
    recurso.refresh_from_db()
    return recurso


def _obra(client):
    sopa = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    return sopa, sopa.select_one("section.portada-arte picture.portada-imagen")


def _srcsets(picture):
    return [s["srcset"] for s in picture.select("source")] + [picture.img.get("srcset", "")]


def test_sin_imagen_elegida_la_portada_lleva_la_lamina(client):
    """El colectivo aún no tiene la suya: la portada estrena la lámina, en AVIF y WebP, con
    su recorte vertical para el teléfono. Es ambiente: no se anuncia."""
    _, picture = _obra(client)
    fuentes = picture.select("source")
    assert [(f.get("media"), f["type"]) for f in fuentes] == [
        (PORTADA_TELEFONO, "image/avif"),
        (PORTADA_TELEFONO, "image/webp"),
        (None, "image/avif"),
        (None, "image/webp"),
    ]
    assert "lamina-alta-1080.avif 1080w" in fuentes[0]["srcset"]
    assert "lamina-ancha-2400.webp 2400w" in fuentes[3]["srcset"]
    img = picture.img
    assert img["alt"] == ""
    assert img["fetchpriority"] == "high"
    assert not img.has_attr("loading"), "la imagen de la primera vista no espera"


def test_la_lamina_esta_entera_y_cumple_el_presupuesto():
    """Hasta 300 KB en escritorio y 150 KB en el teléfono (cálculo del tablero, a partir de la
    meta de carga de 2,5 s). Cada copia que nombra la etiqueta existe, con su tamaño."""
    for forma, tope in (("ancha", 300), ("alta", 150)):
        for ancho, alto in LAMINA[forma]:
            for ext in ("avif", "webp"):
                archivo = ESTATICOS / f"lamina-{forma}-{ancho}.{ext}"
                assert archivo.exists(), f"falta {archivo.name}"
                assert archivo.stat().st_size <= tope * 1024, f"{archivo.name} pasa de {tope} KB"
                with Image.open(archivo) as im:
                    assert im.size == (ancho, alto), archivo.name
    assert (ESTATICOS / "lamina-ancha-1440.jpg").exists(), (
        "falta la reserva para navegadores viejos"
    )


def test_la_imagen_elegida_reemplaza_a_la_lamina_y_nunca_sirve_el_original(client):
    obra = _recurso()
    perfil = SiteProfile.load()
    perfil.hero_image = obra
    perfil.save()
    _, picture = _obra(client)
    fuentes = picture.select("source")
    assert [(f.get("media"), f["type"]) for f in fuentes] == [
        (None, "image/avif"),
        (None, "image/webp"),
    ]
    assert fuentes[0]["srcset"].endswith("obra__portada-jpg-1500w.avif 1500w")
    assert "obra__portada-jpg-640w.webp 640w" in fuentes[1]["srcset"]
    original = obra.file.url
    assert all(f"{original} " not in srcset for srcset in _srcsets(picture))
    assert picture.img["src"] != original
    assert picture.img["alt"] == "Lectura en la plaza", "la obra del colectivo dice algo"
    assert "lamina" not in str(picture)


def test_el_recorte_del_telefono_va_primero_con_su_media(client):
    perfil = SiteProfile.load()
    perfil.hero_image = _recurso("ancha.jpg")
    perfil.hero_image_phone = _recurso("alta.jpg", (700, 1400))
    perfil.save()
    _, picture = _obra(client)
    fuentes = [(f.get("media"), f["type"], f["srcset"]) for f in picture.select("source")]
    assert [m for m, _, _ in fuentes] == [PORTADA_TELEFONO, PORTADA_TELEFONO, None, None]
    assert "alta__portada-jpg-700w.avif 700w" in fuentes[0][2]
    assert "ancha__portada-jpg-1500w.avif 1500w" in fuentes[2][2]


def test_la_imagen_para_compartir_no_es_la_obra(client):
    """og_image lleva el nombre escrito: bajo el logo lo repetiría."""
    perfil = SiteProfile.load()
    perfil.og_image = _recurso("tarjeta.jpg", (1200, 630))
    perfil.save()
    _, picture = _obra(client)
    assert "lamina-ancha-2400.avif" in str(picture)
    assert "tarjeta" not in str(picture)


@pytest.mark.parametrize(
    ("ancho", "copias"),
    [
        (3000, [640, 960, 1080, 1440, 1920, 2560]),
        (1500, [640, 960, 1080, 1440, 1500]),
        (300, [300]),
    ],
)
def test_las_copias_de_portada_no_pasan_del_original(ancho, copias):
    """Nunca suben de tamaño, y si el original cabe, hay una copia a su ancho: así la portada
    no tiene que servir el archivo subido."""
    assert MediaAsset(width=ancho).portada_widths() == copias


def test_las_copias_se_hacen_al_elegir_la_obra_y_una_sola_vez(monkeypatch):
    obra = _recurso()
    almacen = obra.file.storage
    assert not almacen.exists(obra._portada_name(1500, "avif")), "solo la obra elegida tiene copias"
    perfil = SiteProfile.load()
    perfil.hero_image = obra
    perfil.save()
    for ancho in obra.portada_widths():
        for ext in ("avif", "webp"):
            assert almacen.exists(obra._portada_name(ancho, ext))
    with Image.open(almacen.path(obra._portada_name(1080, "avif"))) as copia:
        assert (copia.format, copia.size) == ("AVIF", (1080, 648))
    guardadas = []
    monkeypatch.setattr(almacen, "save", lambda *a, **k: guardadas.append(a))
    perfil.save()
    assert not guardadas, "las copias que ya existen no se rehacen"


def test_al_cambiar_el_archivo_de_la_obra_se_rehacen_sus_copias():
    obra = _recurso("primera.jpg")
    perfil = SiteProfile.load()
    perfil.hero_image = obra
    perfil.save()
    almacen = obra.file.storage
    vieja = obra._portada_name(1500, "avif")
    buffer = BytesIO()
    Image.new("RGB", (1200, 800), (10, 20, 30)).save(buffer, format="JPEG")
    obra.file = SimpleUploadedFile("segunda.jpg", buffer.getvalue(), content_type="image/jpeg")
    obra.save()
    obra.refresh_from_db()
    assert not almacen.exists(vieja), "las copias del archivo anterior quedaron huérfanas"
    assert almacen.exists(obra._portada_name(1200, "avif"))


def test_borrar_la_obra_borra_sus_copias():
    obra = _recurso()
    perfil = SiteProfile.load()
    perfil.hero_image = obra
    perfil.save()
    almacen = obra.file.storage
    copias = [obra._portada_name(w, e) for w in obra.portada_widths() for e in ("avif", "webp")]
    assert all(almacen.exists(c) for c in copias)
    obra.delete()
    assert not any(almacen.exists(c) for c in copias)
    assert SiteProfile.load().hero_image is None, "la portada vuelve a la lámina"


def test_la_obra_se_elige_desde_el_panel(client, django_user_model):
    """Los dos campos están en el perfil del sitio, con su nombre en castellano y el buscador
    de la biblioteca de imágenes, como la imagen para compartir."""
    assert {"hero_image", "hero_image_phone"} <= set(SiteProfileAdmin.autocomplete_fields)
    SiteProfile.load()
    client.force_login(django_user_model.objects.create_superuser("admin", "a@example.com", "x"))
    respuesta = client.get(reverse("admin:showcase_siteprofile_change", args=[1]))
    assert respuesta.status_code == 200
    sopa = BeautifulSoup(respuesta.content, "html.parser")
    for campo, rotulo in (
        ("hero_image", "Imagen de portada"),
        ("hero_image_phone", "Imagen de portada para el teléfono"),
    ):
        assert sopa.select_one(f"select#id_{campo}") is not None
        assert sopa.select_one(f"label[for=id_{campo}]").get_text(strip=True).rstrip(":") == rotulo


def test_la_hoja_y_lo_que_sigue_suben_en_el_telon(client):
    sopa, _ = _obra(client)
    hijos = list(sopa.select_one("main").find_all(recursive=False))
    assert [h.name for h in hijos] == ["section", "div"]
    assert "portada-arte" in hijos[0]["class"] and "portada-telon" in hijos[1]["class"]
    assert hijos[1].find("section", recursive=False)["class"] == ["hero"]
    assert hijos[1].select_one("section.home-cierre") is not None


def test_saltar_al_contenido_lleva_a_la_hoja(client):
    """En la portada, «Saltar al contenido» salta la obra y lleva a la hoja; en las demás
    páginas, al principio de <main>."""
    portada = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    assert portada.select_one("a.skip")["href"] == "#contenido"
    assert portada.select_one("#contenido")["class"] == ["hero"]
    otra = BeautifulSoup(client.get(reverse("content:text_archive")).content, "html.parser")
    assert otra.select_one("a.skip")["href"] == "#main"


def test_los_posteres_de_la_tirada_esperan_y_el_de_la_ficha_no(client):
    """En la portada la tirada queda bajo la obra y la hoja: sus pósters cargan al acercarse y no
    le quitan ancho de banda a la obra. En la ficha del registro el póster está arriba."""
    from apps.media.models import Recording

    registro = Recording.objects.create(
        slug="recital",
        title="Recital",
        embed_url="https://youtu.be/xyz123ab",
        poster=_recurso("poster.jpg", (1200, 675), alt="Recital"),
        published=True,
        featured=True,
    )
    portada = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    assert portada.select_one(".tirada .pliego-placa img")["loading"] == "lazy"
    ficha = BeautifulSoup(client.get(registro.get_absolute_url()).content, "html.parser")
    assert not ficha.select_one(".player-frame img").has_attr("loading")
