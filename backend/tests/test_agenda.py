from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Event, EventPhoto, Milestone
from apps.media.models import MediaAsset, Recording

pytestmark = pytest.mark.django_db


def make_event(**kwargs):
    n = Event.objects.count()
    defaults = {
        "slug": f"evento-{n}",
        "title": f"Evento {n}",
        "starts_at": timezone.now() + timedelta(days=7),
        "published": True,
    }
    defaults.update(kwargs)
    return Event.objects.create(**defaults)


def make_photo(event, position=0):
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (40, 25), (10, 20, 30)).save(buffer, format="JPEG")
    asset = MediaAsset(alt_text=f"foto-{event.slug}-{position}")
    asset.file.save(f"foto-{event.slug}-{position}.jpg", ContentFile(buffer.getvalue()))
    return EventPhoto.objects.create(event=event, asset=asset, position=position)


def test_agenda_lists_upcoming_published_only(client):
    upcoming = make_event(slug="proximo", title="Evento Próximo")
    make_event(slug="pasado", title="Evento Pasado", starts_at=timezone.now() - timedelta(days=3))
    make_event(slug="oculto", title="Evento Oculto", published=False)
    resp = client.get(reverse("agenda:agenda"))
    assert resp.status_code == 200
    assert b"Evento Pr\xc3\xb3ximo" in resp.content
    assert b"Evento Pasado" not in resp.content
    assert b"Evento Oculto" not in resp.content
    assert upcoming.get_absolute_url().encode() in resp.content


def test_trayectoria_groups_past_events_and_milestones(client):
    past = make_event(
        slug="realizado", title="Recital Realizado", starts_at=timezone.now() - timedelta(days=10)
    )
    make_event(slug="futuro", title="Evento Futuro")
    Milestone.objects.create(year=2019, title="Fundación del grupo")
    resp = client.get(reverse("agenda:trayectoria"))
    assert resp.status_code == 200
    assert b"Recital Realizado" in resp.content
    assert b"Evento Futuro" not in resp.content
    assert b"Fundaci\xc3\xb3n del grupo" in resp.content
    assert str(past.starts_at.year).encode() in resp.content


def test_event_detail_404_when_unpublished(client):
    event = make_event(slug="privado", published=False)
    assert client.get(reverse("agenda:event_detail", args=[event.slug])).status_code == 404


def test_event_detail_shows_photos_participants_and_recordings(client):
    from apps.people.models import Contributor

    event = make_event(slug="completo", title="Evento Completo")
    make_photo(event)
    member = Contributor.objects.create(slug="participante", display_name="Poeta Participante")
    event.participants.add(member)
    Recording.objects.create(
        slug="registro-evento",
        title="Registro Del Evento",
        embed_url="https://example.com/v",
        published=True,
        event=event,
    )
    Recording.objects.create(
        slug="registro-oculto",
        title="Registro Oculto",
        embed_url="https://example.com/v2",
        event=event,
    )
    resp = client.get(reverse("agenda:event_detail", args=[event.slug]))
    assert b"Poeta Participante" in resp.content
    assert b"Registro Del Evento" in resp.content
    assert b"Registro Oculto" not in resp.content
    assert b"photo-grid" in resp.content


def test_gallery_lists_only_events_with_photos(client):
    with_photos = make_event(slug="con-fotos", title="Evento Con Fotos")
    make_photo(with_photos)
    make_event(slug="sin-fotos", title="Evento Sin Fotos")
    resp = client.get(reverse("agenda:gallery"))
    assert b"Evento Con Fotos" in resp.content
    assert b"Evento Sin Fotos" not in resp.content


def test_home_shows_next_event_and_stats(client):
    make_event(slug="siguiente", title="Actividad Siguiente")
    make_event(slug="hecho", title="Hecho", starts_at=timezone.now() - timedelta(days=5))
    resp = client.get(reverse("content:home"))
    assert b"Actividad Siguiente" in resp.content
    assert b"evento realizado" in resp.content  # stats strip


def test_event_absolute_url(client):
    event = make_event(slug="ruta")
    assert event.get_absolute_url() == reverse("agenda:event_detail", args=["ruta"])
