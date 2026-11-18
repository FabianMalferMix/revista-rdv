"""El adjunto de un envío solo lo descarga quien puede ver los envíos: a un anónimo lo manda al
login y a una autora le responde 404. Si el archivo falta en el disco, también 404. El almacén
privado no da URL pública: al archivo solo se llega por esa vista.
"""

import pytest
from django.urls import reverse

from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db


def test_submission_file_only_for_editors(client, editor, autor):
    from django.core.files.uploadedfile import SimpleUploadedFile

    submission = Submission.objects.create(
        author_name="A",
        author_email="a@a.com",
        type="resena",
        title="Privado",
        body="cuerpo",
        file=SimpleUploadedFile("m.txt", b"contenido-secreto"),
    )
    url = reverse("submissions:file", args=[submission.pk])

    assert client.get(url).status_code == 302  # anónimo → login

    client.force_login(autor)  # staff pero no editor
    assert client.get(url).status_code == 404

    client.force_login(editor)
    resp = client.get(url)
    assert resp.status_code == 200
    assert b"contenido-secreto" in b"".join(resp.streaming_content)


def test_a_submission_file_missing_from_disk_is_a_404(client, editor, caplog):
    """Si el adjunto falta en el disco, quien puede ver los envíos recibe un 404, no un
    500, y el log lo dice con el número del envío y sin el nombre del archivo, que lo puso
    quien envió la propuesta. Control: con el archivo en su sitio, la descarga sale."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    submission = Submission.objects.create(
        author_name="A",
        author_email="a@a.com",
        type="resena",
        title="Privado",
        body="cuerpo",
        file=SimpleUploadedFile("carta-de-ana.txt", b"contenido-secreto"),
    )
    url = reverse("submissions:file", args=[submission.pk])
    client.force_login(editor)
    response = client.get(url)
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"contenido-secreto"

    submission.file.storage.delete(submission.file.name)
    assert client.get(url).status_code == 404
    (record,) = [r for r in caplog.records if r.name == "apps.submissions.views"]
    assert record.levelname == "WARNING"
    assert str(submission.pk) in record.getMessage()
    assert "carta-de-ana" not in record.getMessage()


def test_private_storage_has_no_public_url():
    from apps.submissions.models import private_storage

    with pytest.raises(ValueError, match="no tienen URL pública"):
        private_storage().url("submissions/2026/11/manuscrito.pdf")
