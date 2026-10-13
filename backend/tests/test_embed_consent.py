"""Los reproductores externos no contactan con terceros sin permiso (hallazgo S-19).

El iframe de YouTube/Vimeo se insertaba con la página, así que el navegador contactaba
con ese tercero —IP, agente de usuario y referente— en cuanto se abría cualquier ficha
de registro y también la PORTADA, sin que nadie hubiera pulsado nada, mientras
/cookies/ afirma que «no compartimos información con terceros».
"""

import re

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


def test_la_ficha_sin_fecha_no_abre_con_un_separador_suelto(client):
    """El · separa fecha y evento; sin fecha no debe encabezar la línea.

    `recorded_on` es opcional y el registro destacado no lo tiene, así que la
    línea de metadatos abría con «· Recital «Nuevas voces»». El separador
    estaba escrito dentro del bloque del evento en vez de depender de que
    hubiera algo delante.
    """
    from tests.factories import make_event

    evento = make_event(title="Recital de prueba")
    registro = _recording(recorded_on=None, event=evento)
    html = client.get(registro.get_absolute_url()).content.decode()

    bloque = re.search(r'<p class="meta">(.*?)</p>', html, re.S)
    assert bloque, "la ficha ya no tiene línea de metadatos"
    texto = re.sub(r"<[^>]+>", "", bloque.group(1)).strip()
    assert not texto.startswith("·"), (
        f"la línea de metadatos abre con un separador suelto: {texto!r}"
    )
    assert "Recital de prueba" in texto, "el evento dejó de mostrarse"


# ── La placa nunca está vacía (ticket 3.4, D10) ───────────────────────────


def _poster(texto="Cartel del recital"):
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image

    from apps.media.models import MediaAsset

    buffer = BytesIO()
    Image.new("RGB", (64, 36), (10, 20, 30)).save(buffer, format="JPEG")
    cartel = MediaAsset(alt_text=texto)
    cartel.file.save("cartel.jpg", ContentFile(buffer.getvalue()))
    return cartel


def test_con_poster_la_placa_lo_ensena_y_es_propio():
    """El póster es una imagen del sitio, nunca la miniatura del proveedor: esa conectaría
    con YouTube antes del clic. Es decorativo: el título ya está en la página."""
    from bs4 import BeautifulSoup
    from django.conf import settings

    placa = BeautifulSoup(_render(_recording(poster=_poster())), "html.parser").select_one(
        ".player-consent"
    )
    imagen = placa.select_one(".riso-duo img")
    assert imagen is not None, "la placa con póster no lo enseña"
    assert imagen["src"].startswith(settings.MEDIA_URL)
    assert imagen["alt"] == ""
    assert placa.select_one(".rec-caratula") is None
    assert "ytimg" not in str(placa) and "youtube.com/vi" not in str(placa)


def test_sin_poster_la_placa_lleva_su_caratula():
    from bs4 import BeautifulSoup

    from tests.factories import make_event

    evento = make_event(title="Recital de la placa")
    placa = BeautifulSoup(
        _render(_recording(title="Lectura sin cartel", event=evento)), "html.parser"
    ).select_one(".player-consent")
    caratula = placa.select_one(".rec-caratula")
    assert caratula is not None, "una placa azul vacía no dice qué registro es"
    assert caratula.select_one(".rec-caratula-titulo").get_text() == "Lectura sin cartel"
    # Sin fecha de grabación, el año sale de su evento.
    from django.utils import timezone

    anio = timezone.localtime(evento.starts_at).year
    assert caratula.select_one(".rotulo").get_text() == f"Video · Recital · {anio}"
    assert caratula["aria-hidden"] == "true", "el título ya se lee en la página"


def test_el_boton_de_reproducir_se_llama_como_el_registro():
    """El botón es un cuadrado con un triángulo: su nombre va en texto oculto."""
    from bs4 import BeautifulSoup

    boton = BeautifulSoup(_render(_recording(title="Recital")), "html.parser").select_one(
        ".embed-play"
    )
    assert boton.get_text(strip=True) == "Reproducir «Recital»"
    assert boton.select_one(".sr-only") is not None
