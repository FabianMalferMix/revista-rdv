"""La portada como obra (D18): la mancheta de afiche con telón que eligió el dueño del sitio
en el tablero de la portada (2026-10-20).

La primera vista es una obra a sangre con el logo al pie; lo que era el titular pasa a la
hoja que sigue. La obra la elige el colectivo en el perfil del sitio y sale en AVIF y WebP,
con un recorte vertical para el teléfono; sin ella, va la lámina del estreno. El alto, el
asomo y el telón están en test_css_sistema.py; la hoja, en test_titular.py.
"""

import gc
from io import BytesIO
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import inspect as django_inspect
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


def test_el_poster_del_destacado_espera_en_la_portada_y_no_en_su_ficha(client):
    """En la portada, el destacado queda bajo la obra y la hoja: su póster carga al acercarse
    y no le quita ancho de banda a la obra. En la ficha del registro está arriba y no espera."""
    from apps.media.models import Recording

    registro = Recording.objects.create(
        slug="recital",
        title="Recital",
        embed_url="https://youtu.be/xyz123ab",
        poster=_recurso("poster.jpg", (1200, 675), alt="Recital"),
        published=True,
    )
    perfil = SiteProfile.load()
    perfil.featured_recording = registro
    perfil.save()
    portada = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    assert portada.select_one(".featured .player-frame img")["loading"] == "lazy"
    ficha = BeautifulSoup(client.get(registro.get_absolute_url()).content, "html.parser")
    assert not ficha.select_one(".player-frame img").has_attr("loading")


def test_sizes_dice_lo_que_mide_pintada(client):
    """Con object-fit: cover la obra se pinta al ancho de la ventana o al alto de la obra por
    su proporción, lo que sea mayor. Con «100vw», a 951 px el navegador bajaba la copia de
    960 para una lámina que se pinta a 1261 px."""
    _, picture = _obra(client)
    telefono, _, escritorio, _ = [f["sizes"] for f in picture.select("source")]
    assert telefono == "max(100vw, 230px, (100vh - 96px) * 0.500)"
    assert escritorio == (
        "(max-width: 719px) max(100vw, 736px, (100vh - 96px) * 1.600), "
        "max(100vw, 736px, (100vh - 112px) * 1.600)"
    )


def test_un_jpg_y_un_png_del_mismo_nombre_no_comparten_copias():
    """Las copias llevan la extensión del original: con «obra.jpg» de obra y «obra.png» de
    recorte, cada una tiene las suyas, y borrar una no se lleva las de la otra."""
    obra = _recurso("obra.jpg")
    buffer = BytesIO()
    Image.new("RGB", (700, 1400), (10, 120, 200)).save(buffer, format="PNG")
    recorte = MediaAsset.objects.create(
        file=SimpleUploadedFile("obra.png", buffer.getvalue(), content_type="image/png"),
        alt_text="Recorte",
    )
    recorte.refresh_from_db()
    perfil = SiteProfile.load()
    perfil.hero_image, perfil.hero_image_phone = obra, recorte
    perfil.save()
    assert obra._portada_name(640, "avif") != recorte._portada_name(640, "avif")
    almacen = obra.file.storage
    with Image.open(almacen.path(recorte._portada_name(640, "avif"))) as copia:
        assert copia.size == (640, 1280), "el teléfono servía las copias de la obra"
    recorte.delete()
    assert all(almacen.exists(obra._portada_name(w, "avif")) for w in obra.portada_widths())


def test_una_obra_transparente_conserva_su_transparencia():
    """Pasada a RGB sin más, lo transparente salía negro y el logo en tinta desaparecía."""
    imagen = Image.new("RGBA", (800, 500), (0, 0, 0, 0))
    imagen.paste((232, 57, 154, 255), (0, 0, 400, 500))
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    obra = MediaAsset.objects.create(
        file=SimpleUploadedFile("calco.png", buffer.getvalue(), content_type="image/png"),
        alt_text="Calco",
    )
    obra.refresh_from_db()
    perfil = SiteProfile.load()
    perfil.hero_image = obra
    perfil.save()
    for ext in ("avif", "webp"):
        with Image.open(obra.file.storage.path(obra._portada_name(800, ext))) as copia:
            assert copia.mode == "RGBA", ext
            assert copia.getpixel((700, 250))[3] == 0, f"{ext}: lo transparente salió opaco"


def _girada():
    """Una foto «de cámara»: 2000 × 1500 guardada de lado, con la etiqueta EXIF que la
    endereza (orientación 6). Derecha mide 1500 × 2000."""
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = BytesIO()
    Image.new("RGB", (2000, 1500), (90, 90, 90)).save(buffer, format="JPEG", exif=exif.tobytes())
    return SimpleUploadedFile("girada.jpg", buffer.getvalue(), content_type="image/jpeg")


def test_al_cambiar_la_obra_por_una_foto_girada_sus_copias_salen_derechas():
    """La señal llega dentro del save(), antes de que strip_metadata enderece la foto y corrija
    su ancho: las copias se calculaban con 2000 px de ancho, agrandadas y con nombres que
    luego nadie servía ni borraba."""
    obra = _recurso()
    perfil = SiteProfile.load()
    perfil.hero_image = obra
    perfil.save()
    obra.file = _girada()
    obra.save()
    obra.refresh_from_db()
    assert (obra.width, obra.height) == (1500, 2000)
    almacen = obra.file.storage
    assert all(almacen.exists(obra._portada_name(w, "avif")) for w in obra.portada_widths())
    assert not almacen.exists(obra._portada_name(1920, "avif")), "una copia agrandada"
    with Image.open(almacen.path(obra._portada_name(1440, "avif"))) as copia:
        assert copia.size == (1440, 1920), "la copia salió de lado"
    copias = [n for n in obra.derivative_names() if almacen.exists(n)]
    obra.delete()
    assert copias and not any(almacen.exists(n) for n in copias)


def test_la_senal_de_la_portada_no_depende_de_la_cache_de_debug():
    """Con DEBUG, Django guarda en una caché cada receptor que conecta, y eso mantenía viva una
    señal conectada con referencia débil. En producción no hay caché: se perdía en silencio.
    Sin la caché, cambiar el archivo de la obra tiene que rehacer sus copias igual."""
    django_inspect._get_func_parameters.cache_clear()
    gc.collect()
    obra = _recurso("primera.jpg")
    perfil = SiteProfile.load()
    perfil.hero_image = obra
    perfil.save()
    buffer = BytesIO()
    Image.new("RGB", (1200, 800), (10, 20, 30)).save(buffer, format="JPEG")
    obra.file = SimpleUploadedFile("segunda.jpg", buffer.getvalue(), content_type="image/jpeg")
    obra.save()
    obra.refresh_from_db()
    assert obra.file.storage.exists(obra._portada_name(1200, "avif"))


def test_un_aviso_no_queda_bajo_la_obra(client):
    """El aviso del boletín se pinta entre la cabecera y <main>; la obra, subida bajo la franja
    de la cabecera, lo tapaba entero. Con aviso, la obra empieza debajo (ver site.css)."""
    respuesta = client.post(
        reverse("community:subscribe"), {"email": "no-es-un-correo", "next": "/"}, follow=True
    )
    sopa = BeautifulSoup(respuesta.content, "html.parser")
    aviso = sopa.select_one("div.mensajes")
    assert aviso is not None and "Revisa el correo ingresado." in aviso.get_text()
    assert aviso.find_next_sibling()["id"] == "main"
    assert sopa.select_one("main > section.portada-arte") is not None
