"""Placeholders de imagen empaquetados y su uso en los perfiles (fotos de demo)."""

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.media.models import MediaAsset
from apps.people.models import Contributor

pytestmark = pytest.mark.django_db

ASSETS = settings.BASE_DIR / "apps" / "content" / "management" / "commands" / "seed_assets"
BUNDLED = [
    "member-fernanda.jpg",
    "member-andres.jpg",
    "member-paula.jpg",
    "event-apertura.jpg",
    "event-publico.jpg",
    "event-cierre.jpg",
    "cover-umbral.jpg",
    "cover-cuadernos.jpg",
    "cover-correspondencias.jpg",
]


def test_bundled_placeholders_exist_and_are_jpeg():
    for name in BUNDLED:
        f = ASSETS / name
        assert f.exists(), name
        assert f.read_bytes()[:3] == b"\xff\xd8\xff", name  # firma JPEG


def test_member_with_photo_renders_avatar_image(client):
    img = (ASSETS / "member-fernanda.jpg").read_bytes()
    asset = MediaAsset.objects.create(
        alt_text="Retrato demo",
        file=SimpleUploadedFile("m.jpg", img, content_type="image/jpeg"),
    )
    Contributor.objects.create(
        slug="con-foto", display_name="Con Foto", is_member=True, photo=asset
    )
    resp = client.get(reverse("people:member_index"))
    # Con foto se muestra <img class="avatar">, no el span de inicial (avatar-fallback).
    assert b'class="avatar"' in resp.content
    assert b"Retrato demo" in resp.content
