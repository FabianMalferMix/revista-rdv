"""El usuario de cada red del colectivo sale de su URL."""

import pytest

from apps.showcase.models import SiteSocialLink


@pytest.mark.parametrize(
    ("url", "usuario"),
    [
        ("https://www.instagram.com/repitentesdelverso/", "@repitentesdelverso"),
        ("https://www.instagram.com/repitentesdelverso/reels/", "@repitentesdelverso"),
        ("https://www.instagram.com/", ""),
    ],
)
def test_el_usuario_de_una_red_sale_de_su_url(url, usuario):
    assert SiteSocialLink(platform="Instagram", url=url).usuario == usuario
