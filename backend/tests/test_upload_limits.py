"""Lo que se sube tiene un tope por campo, y quien se pasa lee cuánto pesa y qué hacer.

Audio hasta 50 MB, PDF hasta 20 MB e imágenes hasta 12 MB; los vídeos se publican por
enlace. Caddy deja pasar algo más por /admin/ que el tope más alto, para que el mensaje del
formulario llegue a verse en vez de un 413 sin cuerpo; esa relación también se prueba aquí.
"""

import io
import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.urls import reverse

from apps.agenda.models import Event
from apps.media import validators
from apps.media.models import Recording
from apps.submissions.forms import ALLOWED_EXTENSIONS, MAX_FILE_MB
from tests.factories import admin_form_fields, make_image

pytestmark = pytest.mark.django_db
MB = 1024 * 1024


def _upload(name, megabytes):
    """Un archivo recién subido que dice pesar `megabytes`, sin ocupar esa memoria."""
    return InMemoryUploadedFile(io.BytesIO(b"ID3"), "file", name, None, int(megabytes * MB), None)


@pytest.mark.parametrize(
    ("validator", "name", "cap"),
    [
        (validators.validate_audio_size, "lectura.mp3", validators.MAX_AUDIO_MB),
        (validators.validate_pdf_size, "libro.pdf", validators.MAX_PDF_MB),
        (validators.validate_image_size, "foto.jpg", validators.MAX_IMAGE_MB),
    ],
)
def test_each_field_has_a_cap_and_says_how_much_the_file_weighs(validator, name, cap):
    validator(_upload(name, cap))  # justo en el tope, pasa
    with pytest.raises(ValidationError) as error:
        validator(_upload(name, cap + 5))
    assert f"pesa {cap + 5},0 MB y el máximo es {cap} MB" in error.value.messages[0]


def test_a_stored_file_is_not_measured_again():
    stored = _upload("lectura.mp3", validators.MAX_AUDIO_MB + 5)
    stored._committed = True
    validators.validate_audio_size(stored)


def test_recordings_take_audio_and_send_video_to_a_link():
    validators.validate_audio_extension(_upload("lectura.mp3", 1))
    with pytest.raises(ValidationError) as error:
        validators.validate_audio_extension(_upload("recital.mp4", 1))
    assert "Enlace para incrustar" in error.value.messages[0]


def test_the_panel_shows_the_size_error_instead_of_saving(client, editor, monkeypatch):
    client.force_login(editor)
    monkeypatch.setattr(validators.validate_audio_size, "megabytes", 0.001)
    data = {"title": "Lectura", "slug": "lectura", "kind": "audio", "position": 0}
    big = SimpleUploadedFile("lectura.mp3", b"ID3" + b"0" * 4096, content_type="audio/mpeg")
    response = client.post("/admin/media/recording/add/", {**data, "file": big})
    assert response.status_code == 200
    assert "el máximo es 0.001 MB" in response.content.decode()
    assert not Recording.objects.exists()
    # Control positivo: dentro del tope, se guarda.
    small = SimpleUploadedFile("lectura.mp3", b"ID3", content_type="audio/mpeg")
    assert client.post("/admin/media/recording/add/", {**data, "file": small}).status_code == 302


def test_an_event_with_forty_photos_is_saved(client, editor):
    """Cada foto suma cinco campos al formulario: con el límite de 200, no pasaban de 35."""
    client.force_login(editor)
    page = client.get("/admin/agenda/event/add/").content.decode()
    data = admin_form_fields(page, "event_form")
    prefix = re.search(r'name="([\w-]+)-TOTAL_FORMS"', page).group(1)
    data.update(
        {
            "title": "Recital con cuarenta fotos",
            "slug": "recital-con-cuarenta-fotos",
            "starts_at_0": "2026-11-20",
            "starts_at_1": "19:30:00",
            f"{prefix}-TOTAL_FORMS": "40",
        }
    )
    for i in range(40):
        # Los cinco campos de cada fila, como los manda el navegador.
        data[f"{prefix}-{i}-id"] = ""
        data[f"{prefix}-{i}-event"] = ""
        data[f"{prefix}-{i}-asset"] = make_image(f"foto-{i}").pk
        data[f"{prefix}-{i}-caption"] = ""
        data[f"{prefix}-{i}-position"] = i
    assert len(data) > 200
    response = client.post("/admin/agenda/event/add/", data)
    errors = BeautifulSoup(response.content, "html.parser").select(".errorlist li")
    assert response.status_code == 302, [e.get_text() for e in errors]
    assert Event.objects.get(slug="recital-con-cuarenta-fotos").photos.count() == 40


def test_the_public_form_help_comes_from_its_limits(client):
    html = client.get(reverse("submissions:submit")).content.decode()
    for extension in ALLOWED_EXTENSIONS:
        assert extension.upper() in html
    assert f"Máximo {MAX_FILE_MB} MB" in html


CADDYFILE = Path(__file__).resolve().parents[2] / "infra" / "caddy" / "Caddyfile"


def _caddy_limit(matcher):
    if not CADDYFILE.exists():
        pytest.skip("el Caddyfile no está en este árbol")
    text = CADDYFILE.read_text(encoding="utf-8")
    return int(re.search(rf"request_body @{matcher} {{\s*max_size (\d+)MB", text).group(1))


def test_caddy_lets_the_panel_reach_the_form_error():
    """El límite de Caddy en /admin/ pasa del tope más alto: si no, el 413 llegaría antes
    que el mensaje del formulario."""
    highest = max(validators.MAX_AUDIO_MB, validators.MAX_PDF_MB, validators.MAX_IMAGE_MB)
    assert _caddy_limit("panel") > highest


def test_caddy_lets_the_public_form_reach_its_error():
    public = _caddy_limit("fuera_del_panel")
    assert MAX_FILE_MB < public < _caddy_limit("panel")


def test_caddy_recognizes_the_panel_by_its_route():
    """Caddy reconoce el panel por su dirección para darle el límite más alto: los dos
    emparejadores siguen a la ruta del panel, no a un literal."""
    if not CADDYFILE.exists():
        pytest.skip("el Caddyfile no está en este árbol")
    text = CADDYFILE.read_text(encoding="utf-8")
    panel = re.search(r"@panel path (\S+)", text).group(1)
    elsewhere = re.search(r"@fuera_del_panel not path (\S+)", text).group(1)
    assert panel == elsewhere == reverse("admin:index") + "*"
