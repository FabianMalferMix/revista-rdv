"""Fábricas de datos compartidas por los tests.

Centralizadas aquí para eliminar el acoplamiento entre módulos de test (antes un
test importaba fábricas de otro) y la duplicación de helpers (hallazgo #20).
"""

from datetime import timedelta
from io import BytesIO

from bs4 import BeautifulSoup
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


def make_image(nombre, alt="Imagen"):
    """Un recurso de imagen real, de 30 × 40, para retratos, cubiertas y logos."""
    buffer = BytesIO()
    Image.new("RGB", (30, 40), (10, 20, 30)).save(buffer, format="JPEG")
    asset = MediaAsset(alt_text=alt)
    asset.file.save(f"{nombre}.jpg", ContentFile(buffer.getvalue()))
    return asset


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


def admin_form_fields(html, form_id):
    """Los campos del formulario con sus valores iniciales, como los enviaría el navegador."""
    form = BeautifulSoup(html, "html.parser").select_one(f"form#{form_id}")
    fields = {}
    for field in form.select("input[name], textarea[name], select[name]"):
        name = field["name"]
        if "__prefix__" in name or field.get("type") in ("submit", "file"):
            continue
        if field.name == "select" and field.has_attr("multiple"):
            chosen = [option["value"] for option in field.select("option[selected]")]
            if chosen:  # sin nada elegido, el navegador no manda el campo
                fields[name] = chosen
        elif field.name == "select":
            chosen = field.select_one("option[selected]")
            fields[name] = chosen["value"] if chosen else ""
        elif field.get("type") == "checkbox":
            if field.has_attr("checked"):
                fields[name] = "on"
        else:
            fields[name] = field.get("value", field.text if field.name == "textarea" else "")
    return fields
