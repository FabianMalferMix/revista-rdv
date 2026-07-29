"""UX y accesibilidad: skip link, buscador overlay, focus, lightbox (Lote UI-3)."""

import pytest
from django.conf import settings
from django.urls import reverse

from tests.test_agenda import make_event, make_photo

pytestmark = pytest.mark.django_db


def test_skip_link_and_main_landmark(client):
    content = client.get(reverse("content:home")).content
    assert b'class="skip" href="#main"' in content
    assert b'<main class="wrap" id="main">' in content


def test_search_results_is_live_overlay(client):
    content = client.get(reverse("content:home")).content
    assert b'aria-live="polite"' in content
    # Un solo contenedor de resultados (el div suelto a ancho completo desapareció).
    assert content.count(b'id="search-results"') == 1


def test_css_has_focus_visible_overlay_and_lightbox():
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    assert ":focus-visible" in css
    assert ".skip" in css
    assert "#search-results{position:absolute" in css
    assert ".lightbox:target" in css


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


def test_home_has_an_h1(client):
    # La portada (la página más enlazada) debe tener su <h1> (SEO + encabezados a11y).
    resp = client.get(reverse("content:home"))
    assert b"<h1" in resp.content


def test_article_card_title_is_h3(client, make_article):
    """El título de tarjeta baja a <h3>: cuelga de secciones <h2>, así la jerarquía
    de encabezados no queda aplanada (hallazgo #13)."""
    from apps.content.models import EditorialStatus

    art = make_article(status=EditorialStatus.PUBLISHED, slug="card-h3", title="Tarjeta H3")
    html = client.get(reverse("content:text_archive")).content.decode()
    assert f'<h3><a href="{reverse("content:article_detail", args=[art.slug])}">' in html


def test_submit_file_help_id_matches_aria_describedby(client):
    """El aria-describedby del input de archivo referencia un id que SÍ existe: el
    <small> de ayuda lleva ese id (antes la referencia ARIA estaba rota, #14)."""
    html = client.get(reverse("submissions:submit")).content.decode()
    assert 'aria-describedby="id_file_helptext"' in html
    assert 'id="id_file_helptext"' in html
