"""Subidas del panel: los FileField no admiten archivos que el navegador ejecutaría.

Caddy sirve `/media/` directamente desde el volumen, fuera de Django y por tanto fuera de
la CSP. Si el panel aceptara un `.html`, se serviría con `Content-Type: text/html` en el
ORIGEN del sitio, y un editor (rol NO superusuario) podría ejecutar JS con la sesión del
administrador y escalar.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory

from apps.media.models import MediaAsset, Recording
from apps.showcase.models import Publication, SiteProfile

pytestmark = pytest.mark.django_db

# Cargas que el navegador ejecutaría si Caddy las sirviera por su extensión.
EJECUTABLES = [
    ("evil.html", b"<script>alert(document.domain)</script>"),
    ("evil.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'),
    ("evil.xhtml", b"<html xmlns='http://www.w3.org/1999/xhtml'><script/></html>"),
]


def _recording_form(upload):
    form_cls = modelform_factory(Recording, fields=["slug", "title", "kind", "file"])
    return form_cls(
        data={"slug": "x", "title": "x", "kind": "audio"},
        files={"file": upload},
    )


@pytest.mark.parametrize(("name", "payload"), EJECUTABLES)
def test_recording_rechaza_archivos_ejecutables(name, payload):
    form = _recording_form(SimpleUploadedFile(name, payload, content_type="text/html"))
    assert not form.is_valid()
    assert "file" in form.errors


def test_recording_acepta_audio_legitimo():
    # La validación no rompe el caso de uso real (un registro de audio).
    form = _recording_form(SimpleUploadedFile("lectura.mp3", b"ID3\x04\x00\x00\x00", "audio/mpeg"))
    assert form.is_valid(), form.errors.as_json()


@pytest.mark.parametrize(("name", "payload"), EJECUTABLES)
def test_publication_pdf_solo_admite_pdf(name, payload):
    form_cls = modelform_factory(Publication, fields=["slug", "title", "pdf"])
    form = form_cls(
        data={"slug": "p", "title": "p"},
        files={"pdf": SimpleUploadedFile(name, payload, content_type="text/html")},
    )
    assert not form.is_valid()
    assert "pdf" in form.errors


def test_dossier_pdf_solo_admite_pdf():
    form_cls = modelform_factory(SiteProfile, fields=["name", "dossier_pdf"])
    form = form_cls(
        data={"name": "Reseñas"},
        files={"dossier_pdf": SimpleUploadedFile("x.html", b"<script>1</script>", "text/html")},
    )
    assert not form.is_valid()
    assert "dossier_pdf" in form.errors


def test_mediaasset_ya_estaba_protegido_por_imagefield():
    """`ImageField` trae `validate_image_file_extension` por su campo de formulario, así que
    un políglota GIF/HTML no se sube por esta vía. Se fija para que pasar el campo a
    FileField no abra el agujero en silencio."""
    form_cls = modelform_factory(MediaAsset, fields=["file", "alt_text"])
    form = form_cls(
        data={"alt_text": "x"},
        files={"file": SimpleUploadedFile("evil.html", b"GIF89a<script>alert(1)</script>")},
    )
    assert not form.is_valid()
    assert "file" in form.errors


# La otra mitad de la defensa son las cabeceras del bloque /media/ del Caddyfile. NO se
# afirman aquí: una aserción sobre su texto probaría la cadena, no el comportamiento. Las
# comprueba el job `prod-runtime` del CI, que levanta Caddy con ese mismo fichero y mira, en
# un archivo servido de verdad, `X-Content-Type-Options: nosniff` y la CSP
# `default-src 'none'; sandbox`.
