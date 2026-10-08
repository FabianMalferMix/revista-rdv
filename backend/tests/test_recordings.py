import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.media.models import Recording
from apps.media.templatetags.embeds import embed_src
from apps.showcase.models import SiteProfile
from tests.factories import make_recording  # noqa: E402

pytestmark = pytest.mark.django_db


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


def test_el_indice_ensena_miniaturas_y_no_reproductores(client):
    """El índice enseña y la ficha reproduce (backlog UX, ticket 2.2).

    La página era una pila de reproductores, uno por pantalla: dos registros medían
    1262 px. Ahora cada registro es una miniatura con su título que lleva a la ficha, y
    en el índice no queda nada que conecte con YouTube o Vimeo, ni siquiera a la espera
    de un clic. Antes esta prueba afirmaba lo contrario (`player-frame` en el índice).
    """
    from bs4 import BeautifulSoup

    from apps.media.models import Recording

    video = make_recording(slug="video", title="Registro En Video")
    audio = make_recording(
        slug="audio",
        title="Registro En Audio",
        kind=Recording.Kind.AUDIO,
        embed_url="",
        file=SimpleUploadedFile("lectura.mp3", b"ID3-fake-bytes"),
    )
    resp = client.get(reverse("media:recording_index"))
    html = resp.content.decode()
    for resto in ("player-frame", "player-consent", "embed-play", "data-embed-src", "<iframe"):
        assert resto not in html, f"el índice todavía emite «{resto}»"
    assert "<audio" not in html and "<video" not in html
    assert "abc123xyz" not in html, "el identificador del video no debe viajar en el índice"

    tarjetas = BeautifulSoup(html, "html.parser").select("li.recording-card")
    assert len(tarjetas) == 2
    assert all(t.select_one(".rec-miniatura") for t in tarjetas)
    enlaces = {t.select_one("h2 a")["href"] for t in tarjetas}
    assert enlaces == {video.get_absolute_url(), audio.get_absolute_url()}
    # Un solo enlace por tarjeta hacia la ficha: la tarjeta entera lo extiende por CSS.
    for tarjeta in tarjetas:
        assert len(tarjeta.select("a")) == 1


def test_la_miniatura_usa_el_cartel_y_sin_cartel_lleva_el_titulo(client):
    """Una placa azul vacía no dice qué registro es (decisión D10: nunca vacía)."""
    from io import BytesIO

    from bs4 import BeautifulSoup
    from django.core.files.base import ContentFile
    from PIL import Image

    from apps.media.models import MediaAsset

    buffer = BytesIO()
    Image.new("RGB", (64, 36), (10, 20, 30)).save(buffer, format="JPEG")
    cartel = MediaAsset(alt_text="Cartel del recital")
    cartel.file.save("cartel.jpg", ContentFile(buffer.getvalue()))
    make_recording(slug="con-cartel", title="Con Cartel", poster=cartel, position=0)
    make_recording(slug="sin-cartel", title="Sin Cartel", position=1)

    sopa = BeautifulSoup(client.get(reverse("media:recording_index")).content, "html.parser")
    con, sin = sopa.select("li.recording-card")
    assert con.select_one(".rec-miniatura img")["alt"] == "Cartel del recital"
    assert con.select_one(".rec-caratula") is None
    placa = sin.select_one(".rec-miniatura .rec-caratula")
    assert placa.get_text() == "Sin Cartel"
    assert placa["aria-hidden"] == "true", "el título ya se lee en el encabezado de la tarjeta"
    assert sin.select_one("img") is None


def test_el_evento_sigue_siendo_un_enlace_propio_en_la_tarjeta(client):
    from datetime import timedelta

    from bs4 import BeautifulSoup

    from apps.agenda.models import Event

    evento = Event.objects.create(
        slug="origen",
        title="Recital Origen",
        starts_at=timezone.now() - timedelta(days=1),
        published=True,
    )
    registro = make_recording(slug="con-evento", title="Con Evento", event=evento)
    tarjeta = BeautifulSoup(
        client.get(reverse("media:recording_index")).content, "html.parser"
    ).select_one("li.recording-card")
    assert [a["href"] for a in tarjeta.select("a")] == [
        registro.get_absolute_url(),
        evento.get_absolute_url(),
    ]


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
    assert b"player-consent" in resp.content, "la ficha es donde se reproduce"
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


def test_podcast_enclosure_url_is_absolute(client):
    """Contrato de podcast (hallazgo #07): el <enclosure> debe llevar URL ABSOLUTA
    (esquema + host) o Apple/Spotify no descargan el audio y el episodio queda mudo."""
    import xml.dom.minidom as minidom
    from urllib.parse import urlparse

    make_recording(
        slug="audio-abs",
        title="Audio Absoluto",
        kind=Recording.Kind.AUDIO,
        embed_url="",
        file=SimpleUploadedFile("abs.mp3", b"ID3-fake-bytes"),
    )
    resp = client.get(reverse("recordings_feed"))
    dom = minidom.parseString(resp.content)
    enclosures = dom.getElementsByTagName("enclosure")
    assert enclosures, "el feed debe emitir <enclosure> para audio con archivo"
    url = enclosures[0].getAttribute("url")
    parsed = urlparse(url)
    assert parsed.scheme in ("http", "https"), f"enclosure no absoluto: {url}"
    assert parsed.netloc, f"enclosure sin host: {url}"
    assert parsed.path.startswith("/media/"), url


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
