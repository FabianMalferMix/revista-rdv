"""Fábricas de datos compartidas por los tests.

Centralizadas aquí para eliminar el acoplamiento entre módulos de test (antes un
test importaba fábricas de otro) y la duplicación de helpers (hallazgo #20).
"""

from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from apps.agenda.models import Event, EventPhoto
from apps.content.models import EditorialStatus
from apps.media.models import MediaAsset, Recording
from apps.showcase.models import Publication


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
    buffer = BytesIO()
    Image.new("RGB", (40, 25), (10, 20, 30)).save(buffer, format="JPEG")
    asset = MediaAsset(alt_text=f"foto-{event.slug}-{position}")
    asset.file.save(f"foto-{event.slug}-{position}.jpg", ContentFile(buffer.getvalue()))
    return EventPhoto.objects.create(event=event, asset=asset, position=position)


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


def make_publication(**kwargs):
    n = Publication.objects.count()
    defaults = {"slug": f"pub-{n}", "title": f"Publicación {n}", "published": True, "year": 2023}
    defaults.update(kwargs)
    return Publication.objects.create(**defaults)


def publish(article):
    """Marca un artículo o poema como publicado (status + published_at)."""
    article.status = EditorialStatus.PUBLISHED
    article.published_at = timezone.now()
    article.save()
    return article
