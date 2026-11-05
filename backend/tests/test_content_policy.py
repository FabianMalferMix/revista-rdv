"""Cada capa que repite la política de contenido dice lo mismo que su fuente
(`config/content_policy.py`): la CSP admite exactamente los reproductores que arma la ficha de un
registro, el panel nombra exactamente a esos proveedores, el editor del cuerpo recibe exactamente lo
que nh3 conserva al guardar, y el panel se reconoce por su dirección, no por un literal.
"""

import re
from urllib.parse import urlsplit

import nh3
import pytest
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.content.sanitize import clean_html
from apps.media.templatetags.embeds import embed_provider, embed_src
from apps.media.validators import validate_audio_extension
from config.content_policy import EMBED_PROVIDERS
from tests.factories import make_recording, soup

pytestmark = pytest.mark.django_db

# Un enlace de cada proveedor, como lo pega quien sube un registro.
LINKS = {
    "YouTube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "Vimeo": "https://vimeo.com/123456789",
}


def _origin(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _directive(response, name):
    policy = response["Content-Security-Policy"]
    directives = dict(part.strip().split(" ", 1) for part in policy.split(";"))
    return set(directives[name].split())


def test_the_csp_lets_in_exactly_the_players_a_recording_page_builds(client):
    """Cada reproductor que arma la ficha carga en su iframe, y `frame-src` no se abre a nadie
    más: solo 'self', que es el iframe de edición de TinyMCE en el panel."""
    assert set(LINKS) == {provider.name for provider in EMBED_PROVIDERS}, "un proveedor sin enlace"
    players = set()
    for name, link in LINKS.items():
        response = client.get(make_recording(embed_url=link).get_absolute_url())
        player = BeautifulSoup(response.content, "html.parser").select_one("[data-embed-src]")
        assert player is not None, f"la ficha no arma el reproductor de {name}"
        players.add(_origin(player["data-embed-src"]))
        assert _origin(player["data-embed-src"]) in _directive(response, "frame-src"), name
    assert _directive(response, "frame-src") == {"'self'"} | players


def _providers_named_in(text):
    """Los proveedores que nombra una frase del panel: lo que va tras «enlace de», hasta el
    paréntesis o la coma que siguen («YouTube, Vimeo o SoundCloud» da los tres)."""
    names = re.search(r"enlace de (.+?)(?: \(|, en «)", text)
    assert names, f"la frase ya no dice «enlace de…»: {text}"
    return set(re.split(r", | o ", names[1]))


def test_the_panel_names_exactly_the_providers_the_player_embeds(client, editor):
    """La ayuda de los dos campos de la fuente y el error de un archivo de video nombran a los
    proveedores, y cada uno es uno que la ficha sabe reproducir."""
    client.force_login(editor)
    form = soup(client, reverse("admin:media_recording_add"))
    texts = {
        field: form.select_one(f"#id_{field}_helptext").get_text(" ", strip=True)
        for field in ("embed_url", "file")
    }
    with pytest.raises(ValidationError) as error:
        validate_audio_extension(SimpleUploadedFile("recital.mp4", b"\x00"))
    texts["error"] = error.value.messages[0]
    for where, text in texts.items():
        assert _providers_named_in(text) == set(LINKS), where
    for name, link in LINKS.items():
        assert embed_provider(link) == name and embed_src(link), name


# Etiquetas y atributos que se prueban contra nh3, además de los que recibe el editor y de los que
# nh3 admite si no se le dice otra cosa: lo que suele traer un texto pegado de una página o de un
# documento en línea, y lo que no debe pasar nunca.
EXTRA_TAGS = {
    "div",
    "span",
    "font",
    "iframe",
    "script",
    "style",
    "video",
    "audio",
    "source",
    "picture",
    "svg",
    "form",
    "input",
    "button",
    "object",
    "embed",
}
EXTRA_ATTRIBUTES = {
    "class",
    "id",
    "style",
    "srcset",
    "sizes",
    "loading",
    "target",
    "rel",
    "name",
    "role",
    "aria-label",
    "data-id",
    "onclick",
    "hx-get",
}


def _nh3_keeps(tag, attribute=None):
    """Si el saneado conserva esa etiqueta (y ese atributo, con su valor) en un cuerpo."""
    value = "/media/foto.jpg" if attribute in {"href", "src"} else "x"
    attributes = f' {attribute}="{value}"' if attribute else ""
    if tag == "img" and attribute != "src":
        attributes += ' src="/media/foto.jpg"'  # una imagen sin src no se publica
    html = clean_html(f"<{tag}{attributes}>texto</{tag}>")
    found = BeautifulSoup(html, "html.parser").find(tag)
    return found is not None and (attribute is None or found.get(attribute) == value)


def _editor_rules(textarea):
    """{etiqueta: atributos} del `valid_elements` que recibe TinyMCE: «a[href|title],b,…»."""
    rules = {}
    for item in textarea["data-valid-elements"].split(","):
        tag, _, attributes = item.partition("[")
        rules[tag] = set(attributes.rstrip("]").split("|")) - {""}
    return rules


@pytest.mark.parametrize("form", ["admin:content_article_add", "admin:content_page_add"])
def test_the_body_editor_receives_exactly_what_nh3_keeps(client, editor, form):
    """Si el editor admitiera menos, al reeditar una pieza quitaría lo que el servidor guardó, y el
    guardado consolidaría la pérdida; si admitiera más, enseñaría lo que después no se publica."""
    client.force_login(editor)
    textarea = soup(client, reverse(form)).select_one("textarea#id_body")
    editor_rules = _editor_rules(textarea)
    assert {"p", "a", "img"} <= set(editor_rules), "control: el editor recibe la lista"
    tags = set(editor_rules) | set(nh3.ALLOWED_TAGS) | EXTRA_TAGS
    attributes = set().union(*editor_rules.values(), *nh3.ALLOWED_ATTRIBUTES.values())
    attributes |= EXTRA_ATTRIBUTES
    kept = {
        tag: {attribute for attribute in attributes if _nh3_keeps(tag, attribute)}
        for tag in tags
        if _nh3_keeps(tag)
    }
    assert editor_rules == kept


def test_the_panel_is_recognized_by_its_address_not_by_a_literal(client, settings):
    """Con el panel en otra dirección, la CSP relaja los estilos allí y no en /admin/, y robots
    excluye la dirección nueva."""
    settings.ROOT_URLCONF = "tests.urls_panel_elsewhere"
    panel = reverse("admin:index")
    assert panel == "/gestion/"
    login = client.get(reverse("admin:login"))
    assert login.status_code == 200
    assert "'unsafe-inline'" in _directive(login, "style-src")
    assert _directive(client.get("/admin/"), "style-src") == {"'self'"}
    robots = client.get(reverse("robots")).content.decode().splitlines()
    assert "Disallow: /gestion/" in robots
    assert "Disallow: /admin/" not in robots
