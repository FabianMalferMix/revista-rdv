"""Un registro tiene su alternativa en texto junto al reproductor.

La transcripción sale plegada justo después del reproductor, y el poema enlazado, como «Leer el
poema →»; el reproductor se nombra con el título del registro. El panel avisa, sin impedirlo,
al guardar un audio publicado sin transcripción ni poema. La ficha de un poema emite un video
como video.
"""

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus, Poem
from apps.media.models import Recording
from tests.factories import publish

pytestmark = pytest.mark.django_db
TRANSCRIPT = "Primero se presenta el colectivo.\n\nDespués, el poema completo."


def _recording(kind=Recording.Kind.AUDIO, **fields):
    return Recording.objects.create(
        slug="lectura",
        title="Lectura en la plaza",
        kind=kind,
        file=SimpleUploadedFile("lectura.mp3", b"ID3\x04\x00\x00\x00"),
        published=True,
        published_at=timezone.now(),
        **fields,
    )


def _page(client, recording):
    return BeautifulSoup(client.get(recording.get_absolute_url()).content, "html.parser")


def _after(soup, first, then):
    """Si `then` viene después de `first` en el documento."""
    return then in first.find_all_next()


def test_the_transcript_comes_folded_right_after_the_player(client):
    recording = _recording(transcript=TRANSCRIPT, description="Una tarde de agosto.")
    soup = _page(client, recording)
    player, transcript = soup.select_one("audio"), soup.select_one("details.registro-transcripcion")
    assert player["aria-labelledby"] == soup.select_one("h1")["id"] == "registro-titulo"
    assert not transcript.has_attr("open")
    assert transcript.select_one("summary").get_text(strip=True) == "Transcripción"
    assert "Después, el poema completo." in transcript.get_text()
    assert _after(soup, player, transcript)
    assert _after(soup, transcript, soup.find(string="Una tarde de agosto.").parent)


def test_the_linked_poem_is_offered_next_to_the_player(client):
    recording = _recording()
    published = publish(
        Poem.objects.create(slug="umbral", title="Umbral", body="v", recording=recording)
    )
    Poem.objects.create(
        slug="borrador",
        title="Borrador",
        body="v",
        recording=recording,
        status=EditorialStatus.DRAFT,
    )
    soup = _page(client, recording)
    links = [a["href"] for a in soup.select(".registro-poema a")]
    assert links == [published.get_absolute_url()]
    assert soup.select_one(".registro-poema a").get_text(strip=True) == "Leer el poema →"
    assert soup.select_one("details.registro-transcripcion") is None


def _form_data(page, form_id):
    form = BeautifulSoup(page.content, "html.parser").select_one(f"form#{form_id}")
    data = {}
    for field in form.select("input[name], textarea[name], select[name]"):
        if field.get("type") in {"submit", "checkbox", "file"} or field["name"].startswith("_"):
            continue
        if field.name == "select":
            chosen = [option["value"] for option in field.select("option[selected]")]
            if field.has_attr("multiple"):
                if chosen:
                    data[field["name"]] = chosen
                continue
            data[field["name"]] = chosen[0] if chosen else ""
        else:
            data[field["name"]] = field.text if field.name == "textarea" else field.get("value", "")
    return data


@pytest.mark.parametrize(("transcript", "warned"), [("", True), (TRANSCRIPT, False)])
def test_the_panel_warns_about_a_published_audio_with_nothing_to_read(
    client, editor, transcript, warned
):
    recording = _recording()
    url = reverse("admin:media_recording_change", args=[recording.pk])
    client.force_login(editor)
    data = {
        **_form_data(client.get(url), "recording_form"),
        "published": "on",
        "transcript": transcript,
    }
    response = client.post(url, data, follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert any(
        "fue modificado" in m or "se cambió" in m or "correctamente" in m for m in messages
    ), messages
    assert any("sin transcripción ni poema enlazado" in m for m in messages) is warned
    assert Recording.objects.get(pk=recording.pk).transcript == transcript


@pytest.mark.parametrize(
    ("kind", "element"), [(Recording.Kind.VIDEO, "video"), (Recording.Kind.AUDIO, "audio")]
)
def test_the_poem_page_plays_the_recording_with_its_own_element(client, kind, element):
    recording = _recording(kind=kind)
    poem = publish(
        Poem.objects.create(slug="umbral", title="Umbral", body="v", recording=recording)
    )
    block = BeautifulSoup(client.get(poem.get_absolute_url()).content, "html.parser").select_one(
        ".lectura-registro"
    )
    assert [tag.name for tag in block.select("audio, video")] == [element]
