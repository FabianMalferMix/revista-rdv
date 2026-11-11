"""Fábricas de datos y ayudantes compartidos por las pruebas.

Son funciones: cada prueba importa las que usa. Las que crean filas escriben en la base, así que
la prueba que las llama lleva su marca `django_db`.
"""

import itertools
from datetime import timedelta
from io import BytesIO

from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from apps.agenda.models import Event, EventPhoto
from apps.content.models import Article, EditorialStatus, Poem
from apps.media.models import MediaAsset, Recording
from apps.showcase.models import Publication
from apps.site.views import SEARCH_PANEL

# El número de cada slug: no se repite en todo el proceso, aunque una prueba borre filas (el
# recuento de la tabla sí se repetiría).
_sequence = itertools.count()

# Las cabeceras con que htmx pide el panel de la lupa: HX-Target lleva el id de su destino.
# tests/test_search.py comprueba que es el `hx-target` que pinta base.html.
SEARCH_PANEL_HEADERS = {"HX-Request": "true", "HX-Target": SEARCH_PANEL}


def make_event(**kwargs):
    n = next(_sequence)
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
    n = next(_sequence)
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
    n = next(_sequence)
    defaults = {"slug": f"pub-{n}", "title": f"Publicación {n}", "published": True, "year": 2023}
    defaults.update(kwargs)
    return Publication.objects.create(**defaults)


def _dated(fields):
    """Lo publicado, programado o archivado lleva fecha (la restricción de EditorialItem): si la
    prueba no da una, la pieza se publicó ahora o sale mañana."""
    S = EditorialStatus
    if "published_at" not in fields and fields.get("status") in {
        S.PUBLISHED,
        S.ARCHIVED,
        S.SCHEDULED,
    }:
        tomorrow = fields["status"] == S.SCHEDULED
        fields["published_at"] = timezone.now() + timedelta(days=1 if tomorrow else 0)


def make_article(**kwargs):
    """Un artículo, en borrador si la prueba no dice otra cosa: make_article(owner=autor, …)."""
    defaults = {
        "slug": f"articulo-{next(_sequence)}",
        "title": "Título de prueba",
        "body": "palabra " * 250,
        "status": EditorialStatus.DRAFT,
    }
    defaults.update(kwargs)
    _dated(defaults)
    return Article.objects.create(**defaults)


def make_poem(**kwargs):
    """Un poema, en borrador si la prueba no dice otra cosa: make_poem(owner=autor, …)."""
    defaults = {
        "slug": f"poema-{next(_sequence)}",
        "title": "Poema de prueba",
        "body": "Verso uno\n    verso con sangría\n\nVerso final",
        "status": EditorialStatus.DRAFT,
    }
    defaults.update(kwargs)
    _dated(defaults)
    return Poem.objects.create(**defaults)


def make_published_article(**kwargs):
    """Un artículo publicado, con su fecha de publicación: ahora, si la prueba no da otra."""
    kwargs.setdefault("published_at", timezone.now())
    return make_article(status=EditorialStatus.PUBLISHED, **kwargs)


def make_published_poem(**kwargs):
    """Un poema publicado, con su fecha de publicación: ahora, si la prueba no da otra."""
    kwargs.setdefault("published_at", timezone.now())
    return make_poem(status=EditorialStatus.PUBLISHED, **kwargs)


def publish(article):
    """Marca un artículo o poema como publicado (status + published_at)."""
    article.status = EditorialStatus.PUBLISHED
    article.published_at = timezone.now()
    article.save()
    return article


def soup(client, url, **kwargs):
    """La página analizada, como la recibe el navegador. Exige el 200: una página de error no
    es la página que la prueba mira. Los demás argumentos van a `client.get`."""
    response = client.get(url, **kwargs)
    assert response.status_code == 200, f"GET {url}: {response.status_code}"
    return BeautifulSoup(response.content, "html.parser")


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
