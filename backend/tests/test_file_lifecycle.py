"""Ciclo de vida de los archivos subidos (hallazgos S-13 y S-14).

S-13: Django NO borra el archivo del disco al borrar la fila ni al reemplazar el valor
de un `FileField`. Borrar un envío desde el admin dejaba el manuscrito en
`private_media` —y en todos los respaldos posteriores—, así que una petición de
supresión de datos no se cumplía de verdad.

S-14: las derivadas salían limpias porque Pillow no copia el EXIF, pero el ORIGINAL
—el que se sirve a tamaño completo— conservaba geolocalización, fecha y modelo de
cámara. Publicar la ubicación exacta de un recital es una fuga real.
"""

from io import BytesIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from apps.media.models import ImageCleanupError, MediaAsset, Recording
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db


def _jpeg(width=1200, height=800, con_gps=True):
    """JPEG real con un bloque EXIF que incluye coordenadas GPS (Santiago de Chile).

    Se construye con Pillow para no añadir una dependencia de test solo para esto.
    """
    img = Image.new("RGB", (width, height), (120, 130, 140))
    buf = BytesIO()
    if con_gps:
        exif = Image.Exif()
        exif[0x010F] = "ACME"  # Make
        exif[0x0110] = "CamaraX"  # Model
        exif[0x0132] = "2026:07:29 12:00:00"  # DateTime
        exif[0x8825] = {  # GPSInfo
            1: "S",
            2: (IFDRational(33), IFDRational(27), IFDRational(0)),
            3: "W",
            4: (IFDRational(70), IFDRational(39), IFDRational(0)),
        }
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


def _gps():
    return {1: "S", 2: (IFDRational(33), IFDRational(27), IFDRational(0))}


def _avif_con_gps():
    exif = Image.Exif()
    exif[0x8825] = _gps()
    buf = BytesIO()
    Image.new("RGB", (200, 100), (120, 130, 140)).save(buf, format="AVIF", exif=exif)
    return buf.getvalue()


def _jpeg_con_ubicacion_en_xmp():
    """La ubicación solo en el bloque XMP, como la dejan algunos programas de edición."""
    xmp = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
        b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
        b'xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:GPSLatitude="33,27.0S" '
        b'exif:GPSLongitude="70,39.0W"/></rdf:RDF></x:xmpmeta>'
    )
    buf = BytesIO()
    Image.new("RGB", (300, 200), (120, 130, 140)).save(buf, format="JPEG", xmp=xmp)
    return buf.getvalue()


def _jpeg_truncado_con_gps():
    datos = _jpeg()
    return datos[: len(datos) // 2]


def _png_de_64_megapixeles():
    buf = BytesIO()
    Image.new("1", (8000, 8000)).save(buf, format="PNG")
    return buf.getvalue()


def _gif():
    buf = BytesIO()
    Image.new("RGB", (20, 20), (1, 2, 3)).save(buf, format="GIF")
    return buf.getvalue()


def test_el_jpeg_de_prueba_realmente_lleva_gps():
    """Si el fixture no llevara metadatos, los tests de limpieza no probarían nada."""
    exif = Image.open(BytesIO(_jpeg())).getexif()
    assert 0x8825 in exif, "el JPEG de prueba no tiene bloque GPS"
    assert exif.get(0x0110) == "CamaraX"


# ── S-14: metadatos ───────────────────────────────────────


def test_el_original_publicado_no_conserva_gps_ni_camara():
    asset = MediaAsset.objects.create(
        file=SimpleUploadedFile("foto.jpg", _jpeg(), content_type="image/jpeg"),
        alt_text="Recital",
    )
    with asset.file.open("rb") as fh:
        exif = Image.open(fh).getexif()
    assert not exif, "el original sigue publicando metadatos EXIF"


def test_la_imagen_sobrevive_a_la_limpieza():
    """La limpieza no puede corromper ni encoger la foto."""
    asset = MediaAsset.objects.create(
        file=SimpleUploadedFile("foto.jpg", _jpeg(1200, 800), content_type="image/jpeg"),
        alt_text="Recital",
    )
    with asset.file.open("rb") as fh:
        img = Image.open(fh)
        img.load()
    assert (img.width, img.height) == (1200, 800)
    assert asset.width == 1200 and asset.height == 800


def test_una_imagen_sin_metadatos_no_se_recomprime():
    """Idempotencia: el original se reescribe una sola vez, al subirlo; guardar otra vez la
    misma imagen no la recomprime ni degrada su calidad."""
    asset = MediaAsset.objects.create(
        file=SimpleUploadedFile("limpia.jpg", _jpeg(con_gps=False), content_type="image/jpeg"),
        alt_text="Limpia",
    )
    with asset.file.open("rb") as fh:
        antes = fh.read()
    asset.save()
    with asset.file.open("rb") as fh:
        assert fh.read() == antes


def test_los_casos_de_prueba_realmente_llevan_la_ubicacion():
    assert b"GPSLatitude" in _jpeg_con_ubicacion_en_xmp()
    assert 0x8825 in Image.open(BytesIO(_avif_con_gps())).getexif()


@pytest.mark.parametrize(
    "nombre, datos, motivo",
    [
        ("foto.avif", _avif_con_gps, "no admitido"),
        ("foto.jpg", _jpeg_truncado_con_gps, "No se pudo leer la imagen entera"),
        # Django mide la imagen al asignarla y Pillow avisa del tamaño; en producción es solo
        # un aviso en el log, y el validador la rechaza igual.
        pytest.param(
            "enorme.png",
            _png_de_64_megapixeles,
            "40 megapíxeles",
            marks=pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning"),
        ),
    ],
)
def test_lo_que_no_se_puede_limpiar_se_rechaza_al_subirlo(nombre, datos, motivo):
    """Sin estos rechazos, la limpieza no podría reescribir el original y la foto se
    publicaría con su ubicación."""
    asset = MediaAsset(file=SimpleUploadedFile(nombre, datos()), alt_text="Foto")
    with pytest.raises(ValidationError, match=motivo):
        asset.full_clean()


def test_la_ubicacion_solo_en_xmp_tampoco_se_publica():
    asset = MediaAsset.objects.create(
        file=SimpleUploadedFile("xmp.jpg", _jpeg_con_ubicacion_en_xmp()), alt_text="Foto"
    )
    with asset.file.open("rb") as fh:
        datos = fh.read()
    assert b"GPSLatitude" not in datos and b"xmpmeta" not in datos


def test_una_imagen_recien_subida_que_no_se_puede_limpiar_no_se_publica():
    """Una subida que se salta el validador (por código, sin full_clean) falla cerrada: ni la
    fila ni el archivo quedan."""
    with pytest.raises(ImageCleanupError):
        MediaAsset.objects.create(file=SimpleUploadedFile("anim.gif", _gif()), alt_text="Gif")
    assert not MediaAsset.objects.filter(alt_text="Gif").exists()
    assert not [p for p in Path(settings.MEDIA_ROOT).rglob("anim*") if p.is_file()]


def test_el_comando_avisa_de_las_imagenes_que_no_puede_limpiar():
    asset = MediaAsset.objects.create(file=SimpleUploadedFile("foto.jpg", _jpeg()), alt_text="Foto")
    with asset.file.storage.open(asset.file.name, "wb") as fh:
        fh.write(b"ya no es una imagen")
    with pytest.raises(CommandError, match="no se pudieron limpiar"):
        call_command("generate_image_derivatives", verbosity=0)


# ── S-13: archivos huérfanos ──────────────────────────────


def test_borrar_un_envio_borra_el_manuscrito_del_disco():
    sub = Submission.objects.create(
        author_name="Alguien",
        author_email="alguien@example.com",
        type="poesía",
        title="Propuesta",
        body="texto",
        file=SimpleUploadedFile("manuscrito.pdf", b"%PDF-1.4 contenido"),
    )
    storage, name = sub.file.storage, sub.file.name
    assert storage.exists(name)
    sub.delete()
    assert not storage.exists(name), "el manuscrito quedó huérfano en private_media"


def test_borrar_un_recurso_borra_tambien_sus_derivadas():
    asset = MediaAsset.objects.create(
        file=SimpleUploadedFile("foto.jpg", _jpeg(1200, 800), content_type="image/jpeg"),
        alt_text="Recital",
    )
    storage = asset.file.storage
    nombres = [asset.file.name, *asset.derivative_names()]
    existentes = [n for n in nombres if storage.exists(n)]
    assert len(existentes) > 1, "no se generó ninguna derivada; el test no probaría nada"

    asset.delete()
    assert not any(storage.exists(n) for n in existentes)


def test_borrado_masivo_desde_el_admin_tambien_limpia():
    """`QuerySet.delete()` no pasa por `Model.delete()`, pero sí emite post_delete."""
    rec = Recording.objects.create(
        slug="lectura",
        title="Lectura",
        kind=Recording.Kind.AUDIO,
        file=SimpleUploadedFile("lectura.mp3", b"ID3\x04\x00\x00\x00"),
    )
    storage, name = rec.file.storage, rec.file.name
    assert storage.exists(name)
    Recording.objects.filter(pk=rec.pk).delete()
    assert not storage.exists(name)


def test_reemplazar_el_archivo_borra_el_anterior():
    rec = Recording.objects.create(
        slug="lectura",
        title="Lectura",
        kind=Recording.Kind.AUDIO,
        file=SimpleUploadedFile("primera.mp3", b"ID3\x04\x00\x00\x00"),
    )
    storage, anterior = rec.file.storage, rec.file.name
    rec.file = SimpleUploadedFile("segunda.mp3", b"ID3\x04\x00\x00\x01")
    rec.save()
    assert rec.file.name != anterior
    assert not storage.exists(anterior), "el archivo sustituido quedó huérfano"
    assert storage.exists(rec.file.name)
