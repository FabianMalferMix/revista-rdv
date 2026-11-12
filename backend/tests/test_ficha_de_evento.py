"""La ficha de un evento (backlog UX, ticket 5.2).

El afiche era una imagen de 320 px sin pie, y la columna de al lado se quedaba vacía bajo
la descripción; las fotos, miniaturas iguales de 207 × 129 con su pie debajo. Ahora el
afiche va a 420 px como un objeto, con su pie, y a su lado quiénes participan y los
registros; las fotos, en un mosaico de seis, y las demás en «Ver las N fotos».
"""

import re
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.agenda.models import EventPhoto
from apps.people.models import Contributor
from tests import css
from tests.factories import make_event, make_image, make_recording, soup

pytestmark = pytest.mark.django_db

# El contexto de un `--wide` que manda desde un ancho: «@media (min-width:1600px)».
_MIN_WIDTH = re.compile(r"@media \(min-width:(\d+)px\)")


def _evento(**extra):
    return make_event(
        slug="recital", title="Recital", starts_at=timezone.now() - timedelta(days=3), **extra
    )


def _fotos(evento, cuantas, desde=0):
    for i in range(desde, desde + cuantas):
        EventPhoto.objects.create(
            event=evento, asset=make_image(f"foto-{i}"), position=i, caption=f"Foto {i + 1}"
        )


def _sopa(client, evento):
    return soup(client, evento.get_absolute_url())


# ── El afiche y lo que va a su lado ───────────────────────────────────────


def test_el_afiche_lleva_su_pie_con_lo_que_es_y_de_quien(client):
    afiche = make_image("afiche")
    afiche.caption = "Cartel de la lectura"
    afiche.credit = "Diseño: Ana Pérez"
    afiche.save()
    sopa = _sopa(client, _evento(poster=afiche))
    assert "ficha-cabecera--afiche" in sopa.select_one(".ficha-cabecera")["class"], "a 320 px"
    figura = sopa.select_one(".ficha-medio")
    assert figura.name == "figure"
    assert figura.figcaption.get_text() == "Afiche · Cartel de la lectura · Diseño: Ana Pérez"


def test_un_afiche_sin_pie_ni_credito_no_lleva_una_linea_que_solo_diga_afiche(client):
    figura = _sopa(client, _evento(poster=make_image("afiche"))).select_one(".ficha-medio")
    assert figura.img is not None
    assert figura.figcaption is None


def test_quienes_participan_y_los_registros_van_junto_al_afiche(client):
    """Como en la ficha de una publicación: lo que es del evento va al lado de su imagen,
    bajo un rótulo, y no en secciones sueltas debajo de ella."""
    evento = _evento(poster=make_image("afiche"))
    evento.participants.add(
        Contributor.objects.create(slug="poeta", display_name="Poeta Uno", is_member=True)
    )
    make_recording(slug="registro", title="Registro del recital", event=evento)
    make_recording(slug="oculto", title="Registro oculto", event=evento, published=False)
    texto = _sopa(client, evento).select_one(".ficha-cabecera .ficha-texto")
    assert [h2.get_text() for h2 in texto.select("h2.rotulo")] == ["Participan", "Registros"]
    assert texto.find("a", string="Poeta Uno") is not None
    assert texto.find("a", string="Registro del recital") is not None
    assert texto.find("a", string="Registro oculto") is None


# ── Las fotos ─────────────────────────────────────────────────────────────


def test_el_mosaico_lleva_seis_fotos_y_las_demas_se_abren_sin_javascript(client):
    """«Ver las N fotos» es un <details>: se abre sin JavaScript. Cada foto conserva su
    número en la vista ampliada, también las que no caben en el mosaico."""
    evento = _evento()
    _fotos(evento, 8)
    sopa = _sopa(client, evento)
    assert len(sopa.select(".photo-grid > li")) == 6
    mas = sopa.select_one("details.mas-fotos")
    assert mas.summary.get_text() == "Ver las 8 fotos"
    resto = mas.select(".photo-grid-resto > li")
    assert [li.a["aria-label"] for li in resto] == ["Ampliar foto 7 de 8", "Ampliar foto 8 de 8"]
    cuentas = [c.get_text() for c in sopa.select(".lightbox .lightbox-cuenta")]
    assert cuentas == [f"{n} / 8" for n in range(1, 9)]
    # La miniatura abre su vista ampliada, y la vista ampliada vuelve a la galería.
    assert resto[1].a["href"] == "#lb-recital-8"
    assert sopa.select_one("#lb-recital-8 .lightbox-close")["href"] == "#galeria-recital"


def test_con_seis_fotos_o_menos_no_hay_nada_que_desplegar(client):
    evento = _evento()
    _fotos(evento, 6)
    sopa = _sopa(client, evento)
    assert len(sopa.select(".photo-grid > li")) == 6
    assert sopa.select_one(".mas-fotos") is None


def test_el_pie_de_cada_foto_se_lee_en_su_texto_alternativo_y_en_la_vista_ampliada(client):
    """Bajo cada miniatura rompía el mosaico. No se pierde: es el texto alternativo de la
    miniatura y va en el pie de la vista ampliada."""
    evento = _evento()
    _fotos(evento, 3)
    sopa = _sopa(client, evento)
    fotos = sopa.select(".photo-grid > li")
    assert [li.a.img["alt"] for li in fotos] == ["Foto 1", "Foto 2", "Foto 3"]
    assert all(li.find("span", class_="muted", recursive=False) is None for li in fotos)
    ampliada = sopa.select_one("#lb-recital-2")
    assert ampliada.img["alt"] == "Foto 2" and "Foto 2" in ampliada.figcaption.get_text()


def test_la_ficha_cuesta_lo_mismo_con_dos_fotos_que_con_ocho(client):
    """Las fotos y los registros salen de la caché del prefetch: el recorte del mosaico no
    añade consultas, y los registros publicados ya no se piden dos veces."""
    evento = _evento(poster=make_image("afiche"))
    make_recording(slug="registro", title="Registro", event=evento)
    _fotos(evento, 2)
    client.get(evento.get_absolute_url())  # en caliente: el perfil ya existe
    with CaptureQueriesContext(connection) as dos:
        client.get(evento.get_absolute_url())
    _fotos(evento, 6, desde=2)
    with CaptureQueriesContext(connection) as ocho:
        client.get(evento.get_absolute_url())
    assert len(ocho) == len(dos), "una consulta más por foto"
    registros = [q for q in ocho.captured_queries if 'FROM "media_recording"' in q["sql"]]
    assert len(registros) == 1, "los registros se piden dos veces"


@pytest.mark.parametrize(
    "total,first,rest",
    [
        (1, 1440, None),
        (2, 717, 717),
        (3, 958, 476),
        (4, 717, 717),
        (5, 717, 476),
        (6, 958, 476),
        (8, 958, 476),
    ],
)
def test_each_photo_asks_for_the_size_it_takes_in_the_mosaic(total, first, rest):
    """Cada miniatura pide el ancho que ocupa en el mosaico, aquí en una ventana de 1700 px: con
    una foto, todo el carril; con dos, cuatro o cinco, la primera va a medias; con tres o seis,
    a doble tamaño."""
    from apps.agenda.templatetags.gallery import photo_sizes

    assert round(css.sizes_at(photo_sizes(1, total), 1700)) == first
    if rest:
        assert round(css.sizes_at(photo_sizes(total, total), 1700)) == rest


@pytest.mark.parametrize("viewport,width", [(390, 231), (951, 581), (1280, 783), (1700, 958)])
def test_the_first_of_six_photos_asks_for_what_it_paints_at_every_width(viewport, width):
    """El carril encoge con la ventana, menos sus dos medianiles: la primera de seis fotos pide
    sus cuatro columnas de lo que mide el carril a ese ancho, del teléfono al monitor grande."""
    from apps.agenda.templatetags.gallery import photo_sizes

    assert round(css.sizes_at(photo_sizes(1, 6), viewport)) == width


def _wide_lanes():
    """Cada valor de `--wide` en la hoja, en px, con el ancho de ventana desde el que manda."""
    lanes = []
    for block, declaration in css.declarations():
        if declaration.name != "--wide":
            continue
        if not block.context:
            since = 0
        elif len(block.context) == 1 and (cut := _MIN_WIDTH.fullmatch(block.context[0])):
            since = int(cut.group(1))
        else:
            raise AssertionError(f"--wide en un contexto que no sé leer: {block.context}")
        lanes.append((since, int(declaration.value.removesuffix("px"))))
    return sorted(lanes)


def test_the_mosaic_sizes_split_each_lane_of_the_sheet_into_its_columns():
    """Cada miniatura pide su parte del carril (`--wide`) en las columnas del mosaico. Las
    columnas, el hueco y cada valor del carril los decide la hoja, y la etiqueta los repite
    porque no puede leerla: una foto sola pide el carril entero en cada tramo de `--wide`,
    desde que la ventana deja que lo llene hasta el último píxel antes del tramo siguiente."""
    from apps.agenda.templatetags.gallery import MOSAIC_COLUMNS, MOSAIC_GAP, photo_sizes

    rejilla = css.rule((), ".photo-grid, .photo-grid-resto")
    assert rejilla["grid-template-columns"] == f"repeat({MOSAIC_COLUMNS}, minmax(0, 1fr))"
    assert rejilla["gap"] == f"{MOSAIC_GAP}px"
    lanes = _wide_lanes()
    # Control: el valor de siempre y, al menos, el de los monitores grandes.
    assert lanes[0][0] == 0 and len(lanes) > 1, lanes
    widest_gutter = css.px_range(css.tokens()["--gutter"])[1]
    until = [since for since, _ in lanes[1:]] + [None]
    for (since, wide), next_since in zip(lanes, until, strict=True):
        viewport = max(since, wide + 2 * widest_gutter)
        assert next_since is None or viewport < next_since, f"{wide}px no llena el carril"
        widths = [viewport] if next_since is None else [viewport, next_since - 1]
        for width in widths:
            assert css.sizes_at(photo_sizes(1, 1), width) == wide, f"--wide {wide}px a {width}px"
