"""Los reproductores externos no contactan con terceros sin permiso (hallazgo S-19).

El iframe de YouTube/Vimeo se insertaba con la página, así que el navegador contactaba
con ese tercero —IP, agente de usuario y referente— en cuanto se abría cualquier ficha
de registro y también la PORTADA, sin que nadie hubiera pulsado nada, mientras
/cookies/ afirma que «no compartimos información con terceros».
"""

import pytest
from django.template import Context, Template
from django.urls import reverse

from apps.media.models import Recording
from apps.media.templatetags.embeds import embed_provider, embed_src

pytestmark = pytest.mark.django_db

YOUTUBE = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VIMEO = "https://vimeo.com/123456789"


def _render(recording):
    plantilla = Template('{% include "media/partials/_player.html" %}')
    return plantilla.render(Context({"r": recording}))


def _recording(embed_url=YOUTUBE, **extra):
    datos = {
        "slug": "registro",
        "title": "Recital",
        "kind": Recording.Kind.VIDEO,
        "embed_url": embed_url,
        "published": True,
    }
    datos.update(extra)
    return Recording.objects.create(**datos)


def _iframes(html):
    """Iframes REALES del documento. No basta buscar la URL como subcadena: viaja en un
    atributo `data-`, que el navegador nunca descarga por su cuenta."""
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser").find_all("iframe")


def test_el_reproductor_no_trae_iframe_de_entrada():
    html = _render(_recording())
    assert _iframes(html) == [], "el iframe se carga sin que nadie lo pida"
    assert "data-embed-src" in html


def test_el_reproductor_ofrece_el_boton_y_avisa_del_tercero():
    html = _render(_recording())
    assert "embed-play" in html
    assert "data-embed-src" in html
    assert "YouTube" in html, "no se avisa a qué proveedor se conectará"


def test_reconoce_vimeo_como_proveedor():
    html = _render(_recording(embed_url=VIMEO))
    assert "Vimeo" in html
    assert "<iframe" not in html


def test_sin_javascript_queda_un_enlace_al_proveedor():
    """Degradación: sin JS no hay reproductor, pero sí una salida explícita."""
    html = _render(_recording())
    assert "<noscript>" in html
    assert YOUTUBE in html


def test_la_portada_no_contacta_con_terceros(client, make_article):
    """La portada es la página más visitada: era la peor exposición."""
    from apps.showcase.models import SiteProfile

    rec = _recording(featured=True)
    perfil = SiteProfile.load()
    perfil.featured_recording = rec
    perfil.save(update_fields=["featured_recording"])

    resp = client.get(reverse("content:home"))
    assert resp.status_code == 200
    assert _iframes(resp.content) == [], "la portada incrusta un tercero sin permiso"
    assert b"embed-play" in resp.content


def test_la_ficha_del_registro_tampoco(client):
    rec = _recording()
    resp = client.get(reverse("media:recording_detail", args=[rec.slug]))
    assert resp.status_code == 200
    assert _iframes(resp.content) == []
    assert b"embed-play" in resp.content


def test_el_filtro_sigue_resolviendo_la_url_de_incrustacion():
    """La URL correcta debe seguir calculándose: se difiere su uso, no se pierde."""
    assert embed_src(YOUTUBE) == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
    assert embed_src(VIMEO) == "https://player.vimeo.com/video/123456789"
    assert embed_provider(YOUTUBE) == "YouTube"
    assert embed_provider(VIMEO) == "Vimeo"
    assert embed_provider("https://example.com/x") == ""
