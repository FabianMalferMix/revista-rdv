"""Imágenes responsivas (srcset + width/height) y cierre de N+1 — Lote F3-2."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from PIL import Image

from apps.media.models import MediaAsset
from apps.people.models import Contributor

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    """MEDIA_ROOT temporal por test: nombres predecibles (sin sufijo por colisión) y
    sin ensuciar el volumen de medios de desarrollo."""
    settings.MEDIA_ROOT = str(tmp_path)


def _img_upload(name="test.jpg", size=(1000, 600)):
    buf = BytesIO()
    Image.new("RGB", size, (120, 120, 120)).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def _asset(name="test.jpg", size=(1000, 600), alt="alt"):
    a = MediaAsset.objects.create(file=_img_upload(name, size), alt_text=alt)
    a.refresh_from_db()
    return a


def test_derivatives_and_dimensions_populated():
    a = _asset("big.jpg", (1000, 600))
    assert (a.width, a.height) == (1000, 600)  # dimensiones pobladas/reparadas
    ss = a.srcset()
    assert "big__480w.jpg 480w" in ss
    assert "big__960w.jpg 960w" in ss
    assert "big.jpg 1000w" in ss  # el original cierra el srcset
    assert a.file.storage.exists(a._derivative_name(480))
    assert a.file.storage.exists(a._derivative_name(960))
    assert not a.file.storage.exists(a._derivative_name(1440))  # no se sube de tamaño


def test_srcset_empty_for_small_image():
    a = _asset("small.jpg", (300, 200))
    assert (a.width, a.height) == (300, 200)
    assert a.srcset() == ""  # 300 < todos los anchos objetivo → sin derivados


def test_responsive_img_tag_renders_all_attrs():
    a = _asset("t.jpg", (1000, 600), alt="alt X")
    html = Template(
        "{% load images %}{% responsive_img a sizes='50vw' css_class='cover' %}"
    ).render(Context({"a": a}))
    assert 'width="1000"' in html and 'height="600"' in html
    assert 'decoding="async"' in html and 'loading="lazy"' in html
    assert 'srcset="' in html and 'sizes="50vw"' in html
    assert 'class="cover"' in html and 'alt="alt X"' in html


def test_responsive_img_hero_is_not_lazy():
    a = _asset()
    html = Template("{% load images %}{% responsive_img a lazy=False %}").render(
        Context({"a": a})
    )
    assert "loading=" not in html  # imagen destacada (LCP): sin lazy


def test_members_photo_has_no_n_plus_one(django_assert_num_queries):
    for i in range(3):
        Contributor.objects.create(
            slug=f"m{i}",
            display_name=f"M{i}",
            is_member=True,
            photo=_asset(f"m{i}.jpg", (300, 300), alt=f"m{i}"),
        )
    # 1 sola query (con JOIN a photo); acceder a .photo no añade consultas.
    with django_assert_num_queries(1):
        for m in Contributor.members():
            _ = m.photo.file.name if m.photo else None
