"""La navegación del sitio (apps/site/navigation.py): la barra lleva cinco enlaces, ni uno más;
lo que no va en ella está en el mapa del pie, con lo secundario, y el menú del teléfono, un
<details> «Menú», no quita ningún enlace de la página.
"""

import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _nav(content):
    return re.search(rb"<nav[^>]*>.*?</nav>", content, re.S).group(0)


# La barra principal lleva CINCO enlaces (ver «Barra de cinco enlaces y “Dossier”; prensa y
# aliados como línea de respaldo» en docs/deferidos-y-decisiones.md): con nueve, una barra
# solo puede verse como una lista. El dossier va en el botón de la cabecera, fuera de la
# barra. La lista se fija aquí para que ampliarla vuelva a ser una decisión explícita y no
# una acumulación.
NAV_PRINCIPAL = [
    "content:poem_index",
    "content:text_archive",
    "media:recording_index",
    "showcase:publication_index",
    "people:member_index",
]

# Lo que no va en la barra. Ninguno puede quedar huérfano: el mapa del pie los enlaza en
# todas las páginas.
NAV_DEGRADADOS = [
    "showcase:dossier",
    "agenda:agenda",
    "agenda:trayectoria",
    "agenda:gallery",
    "showcase:press_index",
    "showcase:partner_index",
]


def test_nav_curated_for_managers(client):
    """La barra es EXACTAMENTE esos cinco enlaces, ni uno más."""
    nav = _nav(client.get(reverse("site:home")).content)
    for nombre in NAV_PRINCIPAL:
        assert reverse(nombre).encode() in nav, f"falta {nombre} en la barra"
    assert nav.count(b"<a ") == len(NAV_PRINCIPAL), (
        f"la barra tiene {nav.count(b'<a ')} enlaces y debería tener {len(NAV_PRINCIPAL)}"
    )
    # Lo editorial fino y las convocatorias van fuera de la barra principal.
    assert reverse("submissions:submit").encode() not in nav
    assert reverse("content:collection_index").encode() not in nav


def test_every_link_left_out_of_the_bar_is_in_the_footer(client):
    """Degradar un enlace es moverlo, no esconderlo."""
    footer = client.get(reverse("site:home")).content.split(b"site-foot")[1]
    for nombre in NAV_DEGRADADOS:
        assert reverse(nombre).encode() in footer, f"{nombre} quedó huérfano"


def test_footer_keeps_secondary_links(client):
    resp = client.get(reverse("site:home"))
    footer = resp.content.split(b"site-foot")[1]
    assert reverse("submissions:submit").encode() in footer
    assert reverse("content:collection_index").encode() in footer
    assert reverse("recordings_feed").encode() in footer


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
    content = client.get(reverse("site:home")).content
    assert b"nav-disclosure" in content
    assert b"<summary>Men\xc3\xba</summary>" in content
    # El disclosure no quita enlaces del DOM: los 9 están en la página.
    for name in NAV_URLS:
        assert reverse(name).encode() in content
