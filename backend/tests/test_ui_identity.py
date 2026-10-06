"""Identidad tipográfica y nav responsive (Lote UI-2)."""

import re

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
    font = settings.BASE_DIR / "static" / "fonts" / "syne.woff2"
    assert font.exists()
    assert font.read_bytes()[:4] == b"wOF2"  # firma woff2 válida


def test_css_declares_self_hosted_display_font():
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    assert "@font-face" in css
    assert "syne.woff2" in css  # url() relativa (la reescribe WhiteNoise)
    assert "--display" in css
    assert "font-display:swap" in css


def test_no_hay_fuentes_huerfanas():
    """Toda fuente empaquetada debe estar referenciada por el CSS.

    Un .woff2 que ya nadie pide no rompe nada visible: simplemente viaja en la
    imagen y en el manifiesto de estáticos. Fraunces pesaba 67 KB y se quedó
    sin empleo al cambiar la tipografía de titular; esta prueba evita que la
    próxima sustitución deje otro archivo muerto detrás.
    """
    fuentes = sorted((settings.BASE_DIR / "static" / "fonts").glob("*.woff2"))
    assert fuentes, "no hay ninguna fuente empaquetada"
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    huerfanas = [f.name for f in fuentes if f.name not in css]
    assert not huerfanas, f"fuentes que el CSS no referencia: {huerfanas}"


# Las dos parciales que producen una tarjeta de listado. El titular de la tarjeta
# es la superficie donde más se repite la tipografía de titular en todo el sitio.
TARJETAS = [
    "content/partials/_article_card.html",
    "content/partials/_poem_card.html",
]


def _selectores_de_titular(css):
    """Lista de selectores de la regla que fija font-family:var(--display)."""
    m = re.search(r"([^{}]+)\{[^{}]*font-family:var\(--display\)", css)
    assert m, "no se encontró la regla que fija la tipografía de titular"
    return m.group(1)


def test_titulo_de_tarjeta_usa_la_tipografia_de_titular():
    """El CSS debe nombrar la etiqueta que la plantilla emite de verdad.

    La regla apuntaba a `.article-card h2` mientras ambas parciales emiten
    `<h3>`, así que el selector estaba muerto y los títulos de todos los
    listados caían a `--serif`, la pila con Georgia. Con una serif de titular
    la diferencia era casi invisible; con cualquier otra familia, evidente.
    """
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    selectores = _selectores_de_titular(css)
    for parcial in TARJETAS:
        html = (settings.BASE_DIR / "templates" / parcial).read_text(encoding="utf-8")
        etiqueta = re.search(r"<(h[1-6])[\s>]", html)
        assert etiqueta, f"{parcial} ya no emite ningún titular"
        assert f".article-card {etiqueta.group(1)}" in selectores, (
            f"{parcial} emite <{etiqueta.group(1)}> pero la regla de titulares "
            f"no lo cubre; el título caerá a la serif del cuerpo"
        )
