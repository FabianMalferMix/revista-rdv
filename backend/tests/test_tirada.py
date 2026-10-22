"""La tirada de registros de la portada (D19): la opción que eligió el dueño del sitio en el
tablero de los registros destacados (2026-10-21).

Cada registro que el colectivo marca como destacado (con su número de orden) es un pliego que
lleva a su ficha: en la portada no se reproduce nada. Hasta cinco; sin ninguno marcado, el
registro destacado del perfil hace de respaldo, y sin registros vuelve el poema destacado.
Nada avanza solo: static/js/registros.js solo cambia atributos. El aspecto está en
test_css_sistema.py.
"""

from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.showcase.models import SiteProfile
from tests.factories import make_event, make_image, make_photo

pytestmark = pytest.mark.django_db

REGISTROS_JS = (
    Path(__file__).resolve().parent.parent / "static" / "js" / "registros.js"
).read_text()


def _registro(slug, **kw):
    datos = {
        "title": slug.capitalize(),
        "embed_url": "https://youtu.be/xyz123ab",
        "published": True,
        "featured": True,
    }
    datos.update(kw)
    return Recording.objects.create(slug=slug, **datos)


def _tirada(client):
    sopa = BeautifulSoup(client.get(reverse("content:home")).content, "html.parser")
    return sopa, sopa.select_one("section.tirada")


def _titulos(tirada):
    return [p["data-titulo"] for p in tirada.select(".pliego")]


def test_salen_los_destacados_publicados_en_su_orden_y_como_mucho_cinco(client):
    for i, slug in enumerate(["f", "e", "d", "c", "b", "a"]):
        _registro(slug, position=i)
    _registro("sin-marcar", featured=False, position=0)
    _registro("sin-publicar", published=False, position=0)
    _, tirada = _tirada(client)
    assert _titulos(tirada) == ["F", "E", "D", "C", "B"]


def test_sin_ninguno_marcado_el_del_perfil_hace_de_respaldo(client):
    perfil = SiteProfile.load()
    perfil.featured_recording = _registro("respaldo", featured=False)
    perfil.save()
    sopa, tirada = _tirada(client)
    assert _titulos(tirada) == ["Respaldo"]
    # Con uno solo no hay flechas, hoja de contactos ni colofón, ni hace falta el guion.
    assert tirada.select("[data-siguiente], .tirada-contactos, .tirada-colofon") == []
    assert sopa.select_one('script[src*="js/registros.js"]') is None


def test_cada_pliego_lleva_a_su_ficha_sin_reproducir_nada(client):
    registro = _registro("recital", title="Recital «Nuevas voces»")
    _registro("umbral", title="«Umbral»", kind=Recording.Kind.AUDIO, position=1)
    sopa, tirada = _tirada(client)
    pliego = tirada.select_one(".pliego")
    # Un solo enlace por pliego: el título, cuya capa cubre la hoja.
    assert [a["href"] for a in pliego.select("a")] == [registro.get_absolute_url()]
    assert pliego.select_one("h3.pliego-titulo").get_text() == "Recital «Nuevas voces»"
    assert pliego.select_one(".pliego-tipo").get_text(strip=True) == "Video"
    assert pliego.select_one(".pliego-folio").get_text() == "Nº 01"
    assert "Escuchar en su ficha" in tirada.select(".pliego")[1].get_text()
    assert not tirada.select("iframe, video, audio, .player-frame, .embed-play, [data-embed-src]")
    assert sopa.select_one('script[src*="js/registros.js"]').has_attr("defer")


def test_la_imagen_es_el_poster_o_la_primera_foto_del_evento(client):
    evento = make_event(slug="noche", title="Noche")
    make_photo(evento, position=1)
    primera = make_photo(evento, position=0)
    _registro("con-poster", poster=make_image("poster-propio"), event=evento)
    _registro("sin-poster", event=evento, position=1)
    _registro("sin-nada", position=2)
    _, tirada = _tirada(client)
    placas = tirada.select(".pliego-placa")
    assert "poster-propio" in placas[0].img["src"]
    assert primera.asset.file.name.rsplit("/", 1)[-1].split(".")[0] in placas[1].img["src"]
    assert "pliego-placa--vacia" in placas[2]["class"] and placas[2].img is None
    assert all(
        img["alt"] == "" and img["loading"] == "lazy" for img in tirada.select(".pliego-placa img")
    )


def test_el_pliego_cita_el_primer_verso_del_poema_que_se_lee(client, make_poem):
    autora = Contributor.objects.create(slug="fs", display_name="Fernanda Soto")
    registro = _registro("recital")
    poema = make_poem(
        title="Umbral",
        body="\n  La casa guarda un idioma\nque nadie habla",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        recording=registro,
    )
    poema.authors.add(autora)
    make_poem(title="Borrador", body="No se ve", recording=registro)
    _, tirada = _tirada(client)
    assert tirada.select_one(".pliego-verso").get_text() == "«La casa guarda un idioma»"
    assert tirada.select_one(".pliego-firma").get_text() == "Fernanda Soto, «Umbral»"


def test_la_ficha_del_pliego_dice_quien_lee_donde_y_cuando(client):
    evento = make_event(
        slug="r", venue_name="Casa del Libro", city="Santiago", starts_at=timezone.now()
    )
    uno = _registro("uno", event=evento, recorded_on=date(2026, 4, 28))
    uno.participants.add(Contributor.objects.create(slug="fs", display_name="Fernanda Soto"))
    dos = _registro("dos", event=evento, position=1)
    dos.participants.add(
        *[Contributor.objects.create(slug=s, display_name=s.upper()) for s in ("pm", "ts")]
    )
    _, tirada = _tirada(client)
    primero, segundo = tirada.select(".pliego")
    assert (
        " ".join(primero.select_one(".pliego-fechador").get_text(" ").split())
        == "Santiago 28 abr 2026"
    )
    datos = primero.select_one(".pliego-datos")
    assert datos.get_text(" ", strip=True).startswith("Lee Fernanda Soto")
    assert datos.span.get_text() == "Casa del Libro, Santiago"
    assert segundo.select_one(".pliego-datos").get_text().startswith("Leen PM, TS")


def test_sin_javascript_estan_todos_y_los_mandos_esperan_al_guion(client):
    for i, slug in enumerate(["a", "b", "c"]):
        _registro(slug, title=f"Registro {slug}", position=i)
    _, tirada = _tirada(client)
    assert tirada["aria-labelledby"] == "tirada-titulo"
    assert tirada.select_one("#tirada-titulo").get_text() == "Registros"
    assert tirada.select_one(".tirada-todos a")["href"] == reverse("media:recording_index")
    # Las flechas y la hoja de contactos llegan escondidas: sin el guion no harían nada.
    assert tirada.select_one(".tirada-mandos").has_attr("hidden")
    assert tirada.select_one(".tirada-contactos").has_attr("hidden")
    siguiente = tirada.select_one("[data-siguiente]")
    assert siguiente["aria-label"] == "Siguiente: «Registro b»"
    assert tirada.select_one("[data-anterior]").has_attr("disabled")
    # La hoja de contactos nombra cada registro por su título.
    assert [c.get_text(strip=True) for c in tirada.select(".tirada-contacto")] == [
        "Registro a",
        "Registro b",
        "Registro c",
    ]
    assert tirada.select_one("[data-anuncio]")["aria-live"] == "polite"
    assert (
        "tres registros elegidos por el colectivo"
        in tirada.select_one(".tirada-colofon").get_text()
    )
    # Nadie lleva aria-current en el HTML: el frente lo pone el guion.
    assert not tirada.select("[aria-current]")


def test_el_guion_no_avanza_solo_ni_escribe_estilos():
    """Nada avanza solo (ningún temporizador que cambie de registro), no se toca la dirección ni
    el historial, y la CSP no admite estilos en línea."""
    assert "setInterval" not in REGISTROS_JS
    for prohibido in (".style", "cssText", 'setAttribute("style"', "location.hash", "history."):
        assert prohibido not in REGISTROS_JS
    assert "prefers-reduced-motion: reduce" in REGISTROS_JS


def test_la_pila_se_reparte_solo_si_se_puede_mover_y_responde_al_dedo():
    """El reparto (D20) se anima solo para quien no pidió menos movimiento. En el teléfono,
    deslizar sobre la pila pasa de registro (a la izquierda, el siguiente), solo con el dedo o
    el lápiz, y un deslizamiento no abre la ficha que quedó debajo."""
    assert "!quieto.matches" in REGISTROS_JS and ".animate(" in REGISTROS_JS
    for evento in ("pointerdown", "pointerup", "pointercancel"):
        assert f"'{evento}'" in REGISTROS_JS
    assert "e.pointerType === 'mouse'" in REGISTROS_JS
    assert "ir(actual + (dx < 0 ? 1 : -1))" in REGISTROS_JS
    assert "e.stopPropagation()" in REGISTROS_JS


@pytest.mark.parametrize(
    ("minutos", "texto"), [(None, ""), (6, "6 min"), (42, "42 min"), (65, "1 h 05 min")]
)
def test_la_duracion_se_lee_en_minutos_y_horas(minutos, texto):
    assert Recording(duration_minutes=minutos).duracion == texto


def test_el_sello_dice_el_tipo_y_la_duracion(client):
    """D21: con la duración cargada, el sello dice «Video · 42 min»; sin ella, solo el tipo. La
    ficha y el índice la enseñan también."""
    con = _registro("con", title="Con duración", duration_minutes=42)
    _registro("sin", title="Sin duración", kind=Recording.Kind.AUDIO, position=1)
    _, tirada = _tirada(client)
    sellos = [s.get_text(strip=True) for s in tirada.select(".pliego-tipo")]
    assert sellos == ["Video · 42 min", "Audio"]
    ficha = BeautifulSoup(client.get(con.get_absolute_url()).content, "html.parser")
    assert ficha.select_one(".kicker").get_text() == "Registro · Video · 42 min"
    indice = client.get(reverse("media:recording_index")).content.decode()
    assert "Video · 42 min" in indice


def test_el_panel_nombra_los_campos_en_castellano(client, django_user_model):
    """D21: los rótulos del registro y del perfil del sitio estaban en inglés («Featured»,
    «Position», «Featured recording»)."""
    registro = _registro("rotulos")
    client.force_login(django_user_model.objects.create_superuser("admin", "a@example.com", "x"))
    paginas = {
        reverse("admin:media_recording_change", args=[registro.pk]): {
            "id_featured": "Destacado",
            "id_position": "Posición",
            "id_duration_minutes": "Duración (minutos)",
            "id_poster": "Póster",
        },
        reverse("admin:showcase_siteprofile_change", args=[SiteProfile.load().pk]): {
            "id_featured_recording": "Registro destacado (respaldo)",
            "id_featured_poem": "Poema destacado",
            "id_location": "Ubicación",
            "id_booking_email": "Correo de gestión",
        },
    }
    for url, rotulos in paginas.items():
        sopa = BeautifulSoup(client.get(url).content, "html.parser")
        for campo, rotulo in rotulos.items():
            assert sopa.select_one(f"label[for={campo}]").get_text(strip=True).rstrip(":") == rotulo
