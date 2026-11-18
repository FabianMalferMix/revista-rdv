"""La vista ampliada de la galería de una actividad: cada miniatura la abre con su ancla y la
vista se cierra volviendo a la galería, sin JavaScript; no promete la semántica de un modal.
"""

import pytest
from django.urls import reverse

from tests.factories import make_event, make_photo

pytestmark = pytest.mark.django_db


def test_event_gallery_renders_lightbox(client):
    event = make_event(slug="con-lightbox", title="Evento Lightbox")
    make_photo(event)
    resp = client.get(reverse("agenda:event_detail", args=[event.slug]))
    assert resp.status_code == 200
    assert b'class="lightbox"' in resp.content
    assert b"#lb-con-lightbox-1" in resp.content  # el thumbnail enlaza al overlay
    assert b'href="#galeria-con-lightbox"' in resp.content  # y el overlay cierra a la sección
    # Vista ampliada honesta: no promete semántica de modal (sin trampa de foco).
    assert b"aria-modal" not in resp.content
    assert b'role="dialog"' not in resp.content
