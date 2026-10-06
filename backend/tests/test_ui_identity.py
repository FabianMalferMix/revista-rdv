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


# El hero de portada trata el lema como titular y las cifras como dato de
# revista. `.stats-strip` se reutiliza tal cual en /dossier/ y /trayectoria/,
# así que la marca `.hero-stats` es la frontera entre un estilo y el otro.


def test_la_cifra_grande_esta_acotada_a_la_portada():
    """Ninguna regla puede agrandar el <strong> de una tira de cifras sin acotarla.

    Si la regla del número grande se moviera de `.hero-stats strong` a
    `.stats-strip strong`, /dossier/ y /trayectoria/ pasarían a mostrar cifras
    de portada sin que nadie lo hubiera pedido. No se comprueba un tamaño
    concreto —puede ajustarse— sino que cualquier tamaño de titular esté
    acotado a la portada.
    """
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    reglas = re.findall(r"([^{}]*strong[^{}]*)\{([^{}]*)\}", css)
    grandes = []
    for selector, cuerpo in reglas:
        if "stats" not in selector:
            continue
        tam = re.search(r"font-size:\s*(\d+)px", cuerpo)
        if tam and int(tam.group(1)) > 24:
            grandes.append(selector.strip())
    assert grandes, "ya no hay ninguna cifra de portada agrandada"
    for selector in grandes:
        assert ".hero-stats" in selector, (
            f"la cifra grande dejó de estar acotada a la portada: «{selector}»; "
            f"así se filtra a /dossier/ y /trayectoria/"
        )


def test_solo_la_portada_usa_la_tira_de_cifras_de_portada():
    """`hero-stats` marca la tira que recibe el estilo de portada."""
    tpl = settings.BASE_DIR / "templates"
    portada = (tpl / "content" / "home.html").read_text(encoding="utf-8")
    assert "stats-strip hero-stats" in portada, "la portada perdió su marca hero-stats"
    for otra in ("showcase/dossier.html", "agenda/trayectoria.html"):
        texto = (tpl / otra).read_text(encoding="utf-8")
        assert "stats-strip" in texto, f"{otra} ya no usa la tira de cifras"
        assert "hero-stats" not in texto, (
            f"{otra} adoptó la marca de portada y heredará la cifra grande"
        )
