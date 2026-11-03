"""Las imágenes se procesan por un solo camino, y fuera de la petición.

Al subirla, la imagen se limpia de metadatos en la misma petición (si no se puede, se rechaza);
cuando el guardado confirma, una tarea hace sus copias y mide el color de su borde. Guardar sin
cambiar el archivo no la decodifica; la portada no abre ninguna imagen, ni siquiera con la caché
caída; y un archivo que no se puede leer queda nombrado en el log y hace fallar el comando.
"""

import logging
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageFile
from PIL.TiffImagePlugin import IFDRational

from apps.media.models import MediaAsset
from apps.media.services import process_image
from apps.showcase.models import SiteProfile
from tests.factories import make_publication

pytestmark = pytest.mark.django_db
BLUE = (31, 115, 199)
# Puerto sin nadie escuchando: la caché de producción con Redis caído.
CACHE_DOWN = {
    "default": {
        "BACKEND": "config.cache.ResilientRedisCache",
        "LOCATION": "redis://127.0.0.1:6399/0",
    }
}


def _jpeg(size=(1200, 800), color=BLUE, gps=False):
    buf = BytesIO()
    exif = Image.Exif()
    if gps:
        exif[0x8825] = {1: "S", 2: (IFDRational(33), IFDRational(27), IFDRational(0))}
    Image.new("RGB", size, color).save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _processed(name, size=(1200, 800)):
    """Una imagen subida, ya confirmada y procesada por la tarea que encola."""
    with TestCase.captureOnCommitCallbacks(execute=True):
        asset = MediaAsset.objects.create(
            file=SimpleUploadedFile(f"{name}.jpg", _jpeg(size)), alt_text=name
        )
    asset.refresh_from_db()
    return asset


def _near(color, rgb):
    return all(abs(int(color[i : i + 2], 16) - c) <= 2 for i, c in zip((1, 3, 5), rgb, strict=True))


@pytest.fixture
def decoded(monkeypatch):
    """Las imágenes que Pillow decodifica (leer solo la cabecera no cuenta)."""
    calls = []
    original = ImageFile.ImageFile.load

    def counting(self, *args, **kwargs):
        calls.append(self.format)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ImageFile.ImageFile, "load", counting)
    return calls


@pytest.fixture
def opened(monkeypatch):
    """Las imágenes que abre Pillow."""
    calls = []
    original = Image.open

    def counting(fp, *args, **kwargs):
        calls.append(getattr(fp, "name", fp))
        return original(fp, *args, **kwargs)

    monkeypatch.setattr(Image, "open", counting)
    return calls


def test_an_upload_is_cleaned_at_once_and_copied_after_commit(
    client, editor, django_capture_on_commit_callbacks
):
    client.force_login(editor)
    upload = SimpleUploadedFile("recital.jpg", _jpeg(gps=True), content_type="image/jpeg")
    with django_capture_on_commit_callbacks() as callbacks:
        response = client.post(
            reverse("admin:media_mediaasset_add"),
            {"file": upload, "alt_text": "Recital", "caption": "", "credit": ""},
        )
    assert response.status_code == 302
    asset = MediaAsset.objects.get(alt_text="Recital")
    storage = asset.file.storage
    with storage.open(asset.file.name) as fh:
        assert not Image.open(fh).getexif(), "the original is served without its location"
    assert asset.metadata_stripped_at is not None
    assert not storage.exists(asset._derivative_name(480)) and asset.border_color == ""

    for callback in callbacks:
        callback()
    asset.refresh_from_db()
    assert storage.exists(asset._derivative_name(480))
    assert storage.exists(asset._derivative_name(960))
    assert _near(asset.border_color, BLUE)


def test_editing_an_image_without_changing_its_file_does_not_decode_it(client, editor, decoded):
    asset = _processed("tapa")
    decoded.clear()
    client.force_login(editor)
    response = client.post(
        reverse("admin:media_mediaasset_change", args=[asset.pk]),
        {"alt_text": "Tapa corregida", "caption": "", "credit": ""},
    )
    assert response.status_code == 302
    assert MediaAsset.objects.get(pk=asset.pk).alt_text == "Tapa corregida"
    assert decoded == []


@override_settings(CACHES=CACHE_DOWN)
def test_the_home_opens_no_image_even_with_the_cache_down(client, opened):
    for n in range(3):
        make_publication(slug=f"pub-{n}", position=n, cover=_processed(f"tapa-{n}", (300, 420)))
    profile = SiteProfile.load()
    profile.hero_image = _processed("obra", (1600, 900))
    with TestCase.captureOnCommitCallbacks(execute=True):
        profile.save()
    opened.clear()
    response = client.get(reverse("content:home"))
    assert response.status_code == 200
    soup = BeautifulSoup(response.content, "html.parser")
    spines = [rect["fill"] for rect in soup.select(".ejemplar-lomo-fondo rect")]
    assert len(spines) == 3 and all(_near(fill, BLUE) for fill in spines)
    assert soup.select_one("picture.portada-imagen source[type='image/avif']")
    assert opened == []


def test_an_unreadable_image_is_a_warning_naming_it_and_the_command_fails(caplog):
    pending = MediaAsset.objects.create(file=SimpleUploadedFile("nueva.jpg", _jpeg()), alt_text="x")
    broken = _processed("rota")
    with broken.file.storage.open(broken.file.name, "wb") as fh:
        fh.write(b"ya no es una imagen")
    MediaAsset.objects.filter(pk=broken.pk).update(border_color="")
    caplog.set_level(logging.WARNING, logger="apps.media.services")

    with pytest.raises(CommandError, match=rf"1 de 2 .*recursos {broken.pk}\)"):
        call_command("generate_image_derivatives", verbosity=0)
    warnings = [r.getMessage() for r in caplog.records if r.name == "apps.media.services"]
    assert len(warnings) == 1
    assert broken.file.name in warnings[0] and f"recurso {broken.pk}" in warnings[0]
    pending.refresh_from_db()
    assert _near(pending.border_color, BLUE), "the other images are still processed"


def test_each_copy_is_resized_once_from_the_next_wider_one(monkeypatch):
    """Una portada de 3000 px: quince copias en siete anchos, cada ancho a partir del anterior."""
    obra = _processed("ancha", (3000, 1800))
    profile = SiteProfile.load()
    profile.hero_image = obra
    profile.save()  # sin confirmar: las copias de portada aún no se hacen
    for name in obra.derivative_names():
        obra.file.storage.delete(name)
    resizes = []
    original = Image.Image.resize

    def recording(self, size, *args, **kwargs):
        resizes.append((self.width, size[0]))
        return original(self, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", recording)
    assert process_image(obra.pk)
    assert resizes == [
        (3000, 2560),
        (2560, 1920),
        (1920, 1440),
        (1440, 1080),
        (1080, 960),
        (960, 640),
        (640, 480),
    ]
    storage = obra.file.storage
    copies = [obra._derivative_name(w) for w in obra.SRCSET_WIDTHS] + [
        obra._portada_name(w, ext) for w in obra.portada_widths() for ext in ("avif", "webp")
    ]
    assert len(copies) == 15 and all(storage.exists(name) for name in copies)
