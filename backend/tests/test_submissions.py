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
    big = SimpleUploadedFile("grande.pdf", b"0" * (11 * 1024 * 1024), content_type="application/pdf")
    form = SubmissionForm(data=_data(), files={"file": big})
    assert not form.is_valid()
    assert "file" in form.errors
