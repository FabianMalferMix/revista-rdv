"""Las copias de cada imagen quedan registradas en el recurso.

El `srcset` sale de ese registro, sin preguntar al almacenamiento en cada página, y al borrar la
imagen se borran las copias registradas: también las de un ancho que ya no se usa, y nunca las
de otra imagen que se llame igual con otra extensión.
"""

from io import BytesIO
from pathlib import PurePosixPath

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.agenda.models import EventPhoto
from apps.media.models import MediaAsset
from tests.factories import make_event, soup

pytestmark = pytest.mark.django_db


def _upload(name, fmt="JPEG", size=(1000, 600)):
    buf = BytesIO()
    Image.new("RGB", size, (120, 130, 140)).save(buf, format=fmt)
    with TestCase.captureOnCommitCallbacks(execute=True):
        asset = MediaAsset.objects.create(
            file=SimpleUploadedFile(name, buf.getvalue()), alt_text=name
        )
    asset.refresh_from_db()
    return asset


def _delete(asset):
    with TestCase.captureOnCommitCallbacks(execute=True):
        asset.delete()


def test_a_page_with_twenty_images_does_not_ask_the_storage(client, monkeypatch):
    event = make_event(slug="recital")
    for n in range(20):
        EventPhoto.objects.create(event=event, asset=_upload(f"foto-{n}.jpg"), position=n)
    asked = []
    original = FileSystemStorage.exists

    def counting(self, name):
        asked.append(name)
        return original(self, name)

    monkeypatch.setattr(FileSystemStorage, "exists", counting)
    page = soup(client, reverse("agenda:event_detail", args=["recital"]))
    srcsets = [img["srcset"] for img in page.select("img[srcset]") if "foto-" in img["srcset"]]
    assert all(any(f"/foto-{n}__240w.jpg 240w" in s for s in srcsets) for n in range(20))
    assert asked == []


def test_deleting_foto_jpg_keeps_the_copies_of_foto_png():
    jpg, png = _upload("foto.jpg"), _upload("foto.png", "PNG")
    storage = png.file.storage
    jpg_path, png_path = PurePosixPath(jpg.file.name), PurePosixPath(png.file.name)
    assert (
        (jpg_path.parent, jpg_path.stem)
        == (png_path.parent, png_path.stem)
        == (jpg_path.parent, "foto")
    )
    png_copies = [png.file.name, *png.derivative_names()]
    jpg_copies = jpg.derivative_names()
    assert len(png_copies) == 4 and len(jpg_copies) == 3
    _delete(jpg)
    assert not any(storage.exists(name) for name in jpg_copies)
    assert all(storage.exists(name) for name in png_copies)


def test_deleting_an_image_deletes_a_copy_of_a_width_no_longer_in_use(monkeypatch):
    """Una copia de un ancho que se dejó de generar sigue en el registro, y se borra con la
    imagen."""
    monkeypatch.setattr(MediaAsset, "SRCSET_WIDTHS", (300, 480))
    asset = _upload("vieja.jpg")
    monkeypatch.undo()
    old_copy = asset._derivative_name(300)
    storage = asset.file.storage
    assert storage.exists(old_copy) and old_copy in asset.derivative_names()
    assert f"{storage.url(old_copy)} 300w" in asset.srcset()
    _delete(asset)
    assert not storage.exists(old_copy)


def test_a_new_file_never_serves_the_copies_of_the_old_one(monkeypatch):
    """Si las copias viejas no se pudieron borrar (un disco de solo lectura), la imagen nueva
    tiene las suyas: el registro empieza de cero al cambiar el archivo."""
    asset = _upload("tapa.jpg")
    old_copies = asset.derivative_names()

    def refuse(self, name):
        raise OSError("disco de solo lectura")

    buf = BytesIO()
    Image.new("RGB", (1000, 600), (200, 30, 30)).save(buf, format="JPEG")
    monkeypatch.setattr(FileSystemStorage, "delete", refuse)
    with TestCase.captureOnCommitCallbacks(execute=True):
        asset.file = SimpleUploadedFile("tapa.jpg", buf.getvalue())
        asset.save()
    monkeypatch.undo()
    asset.refresh_from_db()
    assert all(asset.file.storage.exists(name) for name in old_copies)
    assert len(asset.derivative_names()) == 3
    assert not set(asset.derivative_names()) & set(old_copies)
    assert all(old not in asset.srcset() for old in old_copies)
