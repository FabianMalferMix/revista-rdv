"""La tirada de registros de la portada (D19): la opción que eligió el dueño del sitio en el
tablero de los registros destacados (2026-10-21).

Cada registro que el colectivo marca como destacado (con su número de orden) es un pliego que
lleva a su ficha: en la portada no se reproduce nada. Hasta cinco; sin ninguno marcado, el
registro destacado del perfil hace de respaldo, y sin registros vuelve el poema destacado.
Nada avanza solo: static/js/registros.js solo cambia atributos. El aspecto está en
test_css_sistema.py.
"""

import re
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
from tests import css
from tests.factories import make_event, make_image, make_photo, make_poem
from tests.scripts import taken_from_common

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
    sopa = BeautifulSoup(client.get(reverse("site:home")).content, "html.parser")
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
    # Con uno solo no hay hoja de contactos ni colofón, ni hace falta el guion.
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


def test_el_pliego_cita_el_primer_verso_del_poema_que_se_lee(client):
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


def test_sin_javascript_estan_todos_y_la_hoja_de_contactos_espera_al_guion(client):
    for i, slug in enumerate(["a", "b", "c"]):
        _registro(slug, title=f"Registro {slug}", position=i)
    _, tirada = _tirada(client)
    assert tirada["aria-labelledby"] == "tirada-titulo"
    assert tirada.select_one("#tirada-titulo").get_text() == "Registros"
    assert tirada.select_one(".tirada-todos a")["href"] == reverse("media:recording_index")
    # La hoja de contactos llega escondida: sin el guion no haría nada. Flechas no hay (D29): se
    # navega con la hoja de contactos, que desde 1100 px es un índice al lado de la pila.
    assert tirada.select_one(".tirada-contactos").has_attr("hidden")
    assert tirada.select(".tirada-mandos, [data-siguiente], [data-anterior], .tirada-flecha") == []
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


def test_la_pila_se_reparte_solo_si_se_puede_mover_y_responde_al_dedo():
    """El reparto (D20) se anima solo para quien no pidió menos movimiento. En el teléfono,
    deslizar sobre la pila pasa de registro (a la izquierda, el siguiente). El gesto, y si se
    puede animar, se los da common.js, como a los demás guiones (test_common_js.py); que el gesto
    sea solo del dedo o del lápiz y que un deslizamiento no abra la ficha que quedó debajo lo
    mira la prueba de humo, en el navegador."""
    assert {"canAnimate", "onSwipe"} <= taken_from_common(REGISTROS_JS)
    assert ".animate(" in REGISTROS_JS
    assert "ir(actual + (dx < 0 ? 1 : -1))" in REGISTROS_JS


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


def test_desde_1100_px_la_hoja_de_contactos_es_un_indice_al_lado():
    """D29: la pila sola dejaba unos 360 px vacíos a 1900; la hoja de contactos va a la derecha,
    en columna, y el abanico se ajusta al hueco que deja."""
    indice = ("@media (min-width:1100px)",)
    pie = css.rule(indice, ".tirada.con-js .tirada-pie")
    assert (pie["grid-column"], pie["grid-row"]) == ("3", "2")
    assert css.rule(indice, ".tirada.con-js .tirada-contactos")["flex-direction"] == "column"
    abanico = [
        r
        for r in css.rules()
        if r.context == indice
        and re.search(r"\.pliego\[aria-current\](?: \+ \.pliego)+$", r.selector)
    ]
    assert abanico, "el abanico no se ajusta al índice"
    assert all("var(--libre)" in r["--x"] for r in abanico), [r["--x"] for r in abanico]


def test_the_pile_has_a_place_for_every_recording_in_the_tirada():
    """Cada pliego tiene su lugar en la pila: TOPE_TIRADA − 1 niveles detrás del de arriba y
    otros tantos delante, cada uno con su desplazamiento y su `z-index`. Si sube el tope y la
    hoja no, el pliego que sobra queda tapado bajo el de arriba en el estado inicial."""
    from apps.site.portada import TOPE_TIRADA

    apiladas = [r.selector for r in css.rules() if r.context == () and "z-index" in r]
    detras = [
        nivel.group(1)
        for selector in apiladas
        if (nivel := re.search(r"\.pliego\[aria-current\]((?: \+ \.pliego)+)$", selector))
    ]
    delante = [
        nivel.group(1)
        for selector in apiladas
        if (nivel := re.search(r"\.pliego:has\(((?:\+ \.pliego ?)+)\[aria-current\]\)$", selector))
    ]
    niveles = set(range(1, TOPE_TIRADA))
    assert {nivel.count("+ .pliego") for nivel in detras} == niveles
    assert {nivel.count("+ .pliego") for nivel in delante} == niveles


def test_a_poem_without_byline_is_signed_with_its_title(client):
    """Sin quien lo firme, el pliego cita el poema con su título solo, sin una coma delante."""
    registro = _registro("recital")
    make_poem(
        title="Umbral",
        body="La casa guarda un idioma",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        recording=registro,
    )
    _, tirada = _tirada(client)
    assert tirada.select_one(".pliego-verso").get_text() == "«La casa guarda un idioma»"
    assert tirada.select_one(".pliego-firma").get_text() == "«Umbral»"


def test_the_place_says_what_there_is_without_a_loose_comma(client):
    """El lugar es la sala y la ciudad, con una coma solo si están las dos."""
    sala = make_event(slug="sala", venue_name="Casa del Libro", city="", starts_at=timezone.now())
    ciudad = make_event(slug="ciudad", venue_name="", city="Santiago", starts_at=timezone.now())
    _registro("uno", event=sala)
    _registro("dos", event=ciudad, position=1)
    _, tirada = _tirada(client)
    lugares = [p.select_one(".pliego-datos span").get_text() for p in tirada.select(".pliego")]
    assert lugares == ["Casa del Libro", "Santiago"]
    # Control: la ciudad va también en el fechador, y la sala no.
    fechadores = [p.select_one(".pliego-fechador").get_text(" ") for p in tirada.select(".pliego")]
    assert "Santiago" in fechadores[1] and "Casa del Libro" not in fechadores[0]


def test_a_pliego_title_drops_a_step_past_34_letters(client):
    """El título de un pliego va enorme y reserva dos líneas: con más de 34 letras baja un paso,
    para no pasar de dos. El umbral es el de esta columna; el de la ficha mide otra y no se
    unifican."""
    _registro("justo", title="x" * 34)
    _registro("largo", title="y" * 35, position=1)
    _, tirada = _tirada(client)
    assert ["pliego--largo" in p["class"] for p in tirada.select(".pliego")] == [False, True]


def test_the_colophon_writes_every_possible_count_in_words(client):
    """El colofón cuenta en letras los registros de la tirada, también cuando llega a su tope:
    cada cuenta posible, de dos al tope, tiene su palabra."""
    from apps.site.portada import TOPE_TIRADA
    from apps.site.templatetags.portada import in_words

    sin_palabra = [n for n in range(2, TOPE_TIRADA + 1) if not in_words(n).isalpha()]
    assert not sin_palabra, f"el colofón diría estas cuentas en cifras: {sin_palabra}"
    for i in range(TOPE_TIRADA):
        _registro(f"r{i}", position=i)
    _, tirada = _tirada(client)
    colofon = tirada.select_one(".tirada-colofon-texto").get_text()
    assert f": {in_words(TOPE_TIRADA)} registros elegidos" in colofon
    assert not re.search(r"\d", colofon)


def test_the_recording_dealt_on_top_goes_one_level_over_the_pile():
    """El que se reparte vuelve encima de todos: un nivel sobre el más alto de la pila, que lee
    de la hoja (el `z-index` de cada pliego). El guion no lleva una altura propia que tenga que
    ganarle a mano a la de la hoja."""
    niveles = re.findall(r"zIndex: ([\w.]+)", REGISTROS_JS)
    assert niveles, "el reparto ya no anima la altura de los pliegos"
    assert not [n for n in niveles if n[0].isdigit()], niveles


def test_the_deal_lasts_longer_than_the_rest_of_the_pile_settles():
    """El que pasa arriba sale de la pila y vuelve encima en un poco más de lo que tardan los
    demás en acomodarse (la transición de `translate` de la hoja): si durara menos, llegaría
    antes que los que se apartan."""
    reparto = int(re.search(r"const REPARTO = (\d+);", REGISTROS_JS).group(1))
    movimiento = ("@media (prefers-reduced-motion:no-preference)",)
    transicion = css.rule(movimiento, ".tirada.con-js .pliego")["transition"]
    (traslado,) = [t for t in css.split_commas(transicion) if t.startswith("translate ")]
    duracion = css.resolve(traslado.split(" ", 1)[1])
    veces, ms = re.match(r"calc\((\d+) \* (\d+)ms\)", duracion).groups()
    assert reparto > int(veces) * int(ms), (reparto, duracion)
