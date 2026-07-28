import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.media.models import Recording
from apps.media.templatetags.embeds import embed_src
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db


def make_recording(**kwargs):
    n = Recording.objects.count()
    defaults = {
        "slug": f"registro-{n}",
        "title": f"Registro {n}",
        "embed_url": "https://www.youtube.com/watch?v=abc123xyz",
        "published": True,
        "published_at": timezone.now(),
    }
    defaults.update(kwargs)
    return Recording.objects.create(**defaults)


# ── Filtro de embeds ─────────────────────────────────────────


def test_embed_src_youtube_watch():
    assert (
        embed_src("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
    )


def test_embed_src_youtu_be():
    assert embed_src("https://youtu.be/dQw4w9WgXcQ") == (
        "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
    )


def test_embed_src_vimeo():
    assert embed_src("https://vimeo.com/123456") == "https://player.vimeo.com/video/123456"


def test_embed_src_unknown_and_empty():
    assert embed_src("https://bandcamp.com/track/x") == ""
    assert embed_src("") == ""


# ── Vistas públicas ──────────────────────────────────────────


def test_recording_index_lists_published_only(client):
    make_recording(slug="publico", title="Registro Público")
    make_recording(slug="oculto", title="Registro Oculto", published=False)
    resp = client.get(reverse("media:recording_index"))
    assert resp.status_code == 200
    assert b"Registro P\xc3\xbablico" in resp.content
    assert b"Registro Oculto" not in resp.content
    assert b"player-frame" in resp.content  # embed de YouTube renderizado como iframe


def test_recording_detail_404_when_unpublished(client):
    rec = make_recording(slug="privado", published=False)
    assert client.get(reverse("media:recording_detail", args=[rec.slug])).status_code == 404


def test_recording_detail_renders_player_and_event(client):
    from datetime import timedelta

    from apps.agenda.models import Event

    event = Event.objects.create(
        slug="evento-registro",
        title="Recital Origen",
        starts_at=timezone.now() - timedelta(days=1),
        published=True,
    )
    rec = make_recording(slug="con-evento", title="Con Evento", event=event)
    resp = client.get(reverse("media:recording_detail", args=[rec.slug]))
    assert b"player-frame" in resp.content
    assert b"Recital Origen" in resp.content


# ── Feed podcast ─────────────────────────────────────────────


def test_podcast_feed_only_audio_with_enclosure(client):
    audio = make_recording(
        slug="audio-pod",
        title="Lectura En Audio",
        kind=Recording.Kind.AUDIO,
        embed_url="",
        file=SimpleUploadedFile("lectura.mp3", b"ID3-fake-bytes"),
    )
    make_recording(slug="video-pod", title="Video No Podcast", kind=Recording.Kind.VIDEO)
    resp = client.get(reverse("recordings_feed"))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Lectura En Audio" in content
    assert "Video No Podcast" not in content
    assert "<enclosure" in content
    assert "audio/mpeg" in content
    assert audio.get_absolute_url() in content


def test_home_shows_featured_recording_when_published(client):
    profile = SiteProfile.load()
    rec = make_recording(slug="destacado", title="Registro En Portada")
    profile.featured_recording = rec
    profile.save()
    assert b"Registro En Portada" in client.get(reverse("content:home")).content

    rec.published = False
    rec.save(update_fields=["published"])
    assert b"Registro En Portada" not in client.get(reverse("content:home")).content


# ── Integridad: fuente obligatoria (archivo O embed) a nivel de BD ──────────


def test_recording_db_requires_file_or_embed():
    from django.db import IntegrityError, transaction

    # Sin file ni embed viola el CheckConstraint aunque no se invoque clean()
    # (p. ej. Recording.objects.create directo).
    with pytest.raises(IntegrityError), transaction.atomic():
        Recording.objects.create(slug="sin-fuente", title="Sin fuente")


def test_recording_with_file_only_is_valid():
    r = make_recording(
        slug="solo-archivo",
        embed_url="",
        file=SimpleUploadedFile("registro.mp3", b"audio-bytes"),
    )
    assert r.pk is not None


def test_podcast_feed_emits_itunes_namespace(client):
    import xml.dom.minidom as minidom

    make_recording(slug="audio-1", kind=Recording.Kind.AUDIO)
    resp = client.get(reverse("recordings_feed"))
    assert resp.status_code == 200
    body = resp.content
    minidom.parseString(body)  # XML válido
    assert b'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"' in body
    assert b"<itunes:author>" in body
    assert b"<itunes:category" in body
    assert b"<itunes:explicit>false</itunes:explicit>" in body
