"""Identidad tipográfica y nav responsive (Lote UI-2)."""

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

NAV_URLS = [
    "content:poem_index",
    "people:member_index",
    "agenda:agenda",
    "agenda:trayectoria",
    "agenda:gallery",
    "media:recording_index",
    "showcase:publication_index",
    "showcase:press_index",
    "showcase:dossier",
]


def test_nav_links_intact_in_disclosure(client):
    content = client.get(reverse("content:home")).content
    assert b"nav-disclosure" in content
    assert b"<summary>Men\xc3\xba</summary>" in content
    # El disclosure no quita enlaces del DOM: los 9 siguen presentes.
    for name in NAV_URLS:
        assert reverse(name).encode() in content


def test_font_file_is_bundled():
    font = settings.BASE_DIR / "static" / "fonts" / "fraunces.woff2"
    assert font.exists()
    assert font.read_bytes()[:4] == b"wOF2"  # firma woff2 válida


def test_css_declares_self_hosted_display_font():
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    assert "@font-face" in css
    assert "fraunces.woff2" in css  # url() relativa (la reescribe WhiteNoise)
    assert "--display" in css
    assert "font-display:swap" in css
