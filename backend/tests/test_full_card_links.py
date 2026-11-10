"""Toda la tarjeta es un enlace, con una sola receta: `.enlace-total`.

El enlace principal de la tarjeta lleva la clase; la capa de su ::after cubre la tarjeta, el
elemento de la lista que lo contiene, y los demás enlaces de la tarjeta quedan por encima
(site.css). Antes había cinco recetas, y solo dos subían los enlaces secundarios: un enlace nuevo
dentro de una tarjeta quedaba tapado si nadie se acordaba de subirlo. Que siguen pulsables lo
comprueba en el navegador la prueba de humo (tools/ux/browser-smoke.js).
"""

import re

import pytest
from django.urls import reverse

from apps.content.models import ArticleContributor, Section
from apps.people.models import Contributor
from tests import css
from tests.factories import make_image, make_published_article, make_recording, soup

pytestmark = pytest.mark.django_db

# El enlace principal de cada tarjeta, por la tarjeta.
PRIMARY = {
    ".fila": ".fila-titulo a",
    ".member-card": ".member-card > a",
    ".recording-card": ".recording-card h2 a",
    ".pie-entidad li": ".pie-entidad a",
}

# Un ::after en posición absoluta sobre un enlace: la capa que hace de la tarjeta un enlace.
LINK_LAYER = re.compile(r"(^|[\s>+~])a([.:\[][^\s>+~]*)?::after$")


def test_the_main_link_of_every_card_is_the_full_card_link(client):
    firma = Contributor.objects.create(
        slug="firma", display_name="Firma", is_member=True, photo=make_image("retrato")
    )
    texto = make_published_article(slug="texto", section=Section.objects.create(slug="s", name="S"))
    ArticleContributor.objects.create(article=texto, contributor=firma)
    make_recording(slug="registro")
    seen = dict.fromkeys(PRIMARY, 0)
    for url in (
        reverse("content:text_archive"),
        reverse("people:member_index"),
        reverse("media:recording_index"),
        texto.get_absolute_url(),
    ):
        sopa = soup(client, url)
        for card, primary in PRIMARY.items():
            for link in sopa.select(primary):
                seen[card] += 1
                assert "enlace-total" in link["class"], f"{url}: «{primary}» no es el enlace total"
                assert link.find_parent("li") is not None, (
                    f"{url}: «{primary}» no está en una lista"
                )
        for li in sopa.select("li:has(.enlace-total)"):
            assert len(li.select(".enlace-total")) == 1, (
                f"{url}: una tarjeta con dos enlaces totales"
            )
    # Control: se miraron tarjetas de cada clase.
    assert all(seen.values()), seen


def test_the_sheet_has_one_recipe_for_the_full_card_link():
    layers = sorted(
        selector
        for rule in css.rules()
        if rule.get("position") == "absolute"
        for selector in rule.selectors
        if LINK_LAYER.search(selector) or ".enlace-total::after" in selector
    )
    assert layers == [".enlace-total::after"], f"otras capas de enlace total: {layers}"
