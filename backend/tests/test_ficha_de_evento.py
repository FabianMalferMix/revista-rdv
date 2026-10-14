"""La ficha de un evento (backlog UX, ticket 5.2).

El afiche era una imagen de 320 px sin pie, y la columna de al lado se quedaba vacía bajo
la descripción; las fotos, miniaturas iguales de 207 × 129 con su pie debajo. Ahora el
afiche va a 420 px como un objeto, con su pie, y a su lado quiénes participan y los
registros; las fotos, en un mosaico de seis, y las demás en «Ver las N fotos».
"""

from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.agenda.models import EventPhoto
from apps.people.models import Contributor
from tests.factories import make_event, make_image, make_recording

pytestmark = pytest.mark.django_db


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
    return BeautifulSoup(client.get(evento.get_absolute_url()).content, "html.parser")


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
    evento.participants.add(Contributor.objects.create(slug="poeta", display_name="Poeta Uno"))
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
