import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.submissions.forms import SubmissionForm

pytestmark = pytest.mark.django_db


def _data(**over):
    data = {
        "author_name": "Ana",
        "author_email": "ana@example.com",
        "type": "reseña",
        "title": "Propuesta",
        "body": "Cuerpo de la propuesta.",
        "apodo": "",
    }
    data.update(over)
    return data


def test_valid_form_is_not_spam():
    form = SubmissionForm(data=_data())
    assert form.is_valid(), form.errors
    assert not form.is_spam


def test_submit_page_shows_consent_note(client):
    from django.urls import reverse

    resp = client.get(reverse("submissions:submit"))
    assert resp.status_code == 200
    assert b"pol\xc3\xadtica de privacidad" in resp.content
    assert reverse("content:page_detail", args=["privacidad"]).encode() in resp.content


def test_honeypot_flags_spam():
    form = SubmissionForm(data=_data(apodo="soy-un-bot"))
    assert form.is_valid()
    assert form.is_spam


def test_invalid_type_choice():
    form = SubmissionForm(data=_data(type="inexistente"))
    assert not form.is_valid()
    assert "type" in form.errors


def test_rejects_disallowed_extension():
    upload = SimpleUploadedFile("malware.exe", b"MZ\x90", content_type="application/octet-stream")
    form = SubmissionForm(data=_data(), files={"file": upload})
    assert not form.is_valid()
    assert "file" in form.errors


def test_accepts_allowed_extension():
    upload = SimpleUploadedFile("texto.txt", b"contenido", content_type="text/plain")
    form = SubmissionForm(data=_data(), files={"file": upload})
    assert form.is_valid(), form.errors


def test_rejects_oversized_file():
    big = SimpleUploadedFile(
        "grande.pdf", b"%PDF-" + b"0" * (11 * 1024 * 1024), content_type="application/pdf"
    )
    form = SubmissionForm(data=_data(), files={"file": big})
    assert not form.is_valid()
    assert "file" in form.errors


def test_rejects_content_not_matching_extension():
    """Un archivo con extensión permitida pero contenido de otro tipo (binario
    renombrado) se rechaza por firma, no solo por extensión (hallazgo #08)."""
    fake = SimpleUploadedFile(
        "malicioso.pdf", b"MZ\x90\x00fake-exe", content_type="application/pdf"
    )
    form = SubmissionForm(data=_data(), files={"file": fake})
    assert not form.is_valid()
    assert "file" in form.errors


def test_accepts_pdf_with_valid_signature():
    real = SimpleUploadedFile(
        "doc.pdf", b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ncontenido", content_type="application/pdf"
    )
    form = SubmissionForm(data=_data(), files={"file": real})
    assert form.is_valid(), form.errors


def test_rejects_binary_disguised_as_txt():
    binbytes = SimpleUploadedFile("nota.txt", b"texto\x00\x01binario", content_type="text/plain")
    form = SubmissionForm(data=_data(), files={"file": binbytes})
    assert not form.is_valid()
    assert "file" in form.errors


def test_submit_rate_limited_rehydrates_form(client):
    """Al superar el rate-limit, el formulario conserva lo escrito por el usuario
    (título y cuerpo) en vez de descartarlo — hallazgo #28."""
    from django.urls import reverse

    url = reverse("submissions:submit")
    data = _data(title="Mi Título Único", body="Un cuerpo memorable y distinto.")
    for _ in range(10):  # agota el rate 10/h
        client.post(url, data)
    resp = client.post(url, data)  # 11.º: limitado
    content = resp.content.decode()
    assert "demasiadas propuestas" in content
    assert "Mi Título Único" in content  # el título vuelve rellenado
    assert "Un cuerpo memorable y distinto." in content  # y el cuerpo


# ── Accesibilidad del formulario (backlog UX, ticket 1.11) ──────────────────


def test_el_formulario_dice_que_dato_es_cada_campo(client):
    """`autocomplete` deja que el navegador rellene nombre y correo (WCAG 1.3.5)."""
    from bs4 import BeautifulSoup
    from django.urls import reverse

    soup = BeautifulSoup(client.get(reverse("submissions:submit")).content, "html.parser")
    assert soup.find("input", {"name": "author_name"})["autocomplete"] == "name"
    assert soup.find("input", {"name": "author_email"})["autocomplete"] == "email"
    assert "Campo obligatorio" in soup.select_one(".form-leyenda").get_text()


def test_cada_campo_invalido_apunta_a_un_error_que_existe(client):
    """Django marca el campo con aria-describedby="<id>_error"; ese id debe existir.

    Los errores se pintaban en <p> sueltos, así que la referencia apuntaba a nada: un
    lector de pantalla anunciaba «inválido» sin decir por qué.
    """
    from bs4 import BeautifulSoup
    from django.urls import reverse

    datos = {"author_name": "", "author_email": "no-es-un-correo", "type": "reseña", "title": ""}
    soup = BeautifulSoup(client.post(reverse("submissions:submit"), datos).content, "html.parser")

    invalidos = soup.select('[aria-invalid="true"]')
    assert len(invalidos) >= 3, "se esperaban al menos nombre, correo y título como inválidos"
    for campo in invalidos:
        referencias = campo.get("aria-describedby", "").split()
        assert referencias, f"{campo.get('name')} es inválido y no dice por qué"
        for ref in referencias:
            destino = soup.find(id=ref)
            assert destino is not None, (
                f"aria-describedby de {campo.get('name')} apunta a «{ref}», que no existe"
            )
            assert destino.get_text(strip=True), f"«{ref}» existe pero está vacío"
