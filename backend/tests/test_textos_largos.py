"""Textos y poemas largos de prueba, y lo que destaparon (lo pidió el dueño, 2026-10-14).

`seed_textos_largos` siembra seis textos y cinco poemas cercanos a los reales: una reseña de
once minutos, un ensayo de quince, una entrevista, una crónica, una crítica con todos los
casos límite y una reseña de dos libros; una letanía de 106 versos, un poema en prosa, una
oda de versos que no caben, un poema escalonado y uno breve de título larguísimo.
Recorridos a siete anchos destaparon tres fallos de la sala de lectura que el contenido de
demostración no podía enseñar (las pruebas de la hoja están en `test_css_sistema.py`).
"""

import pytest
from bs4 import BeautifulSoup
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.content.models import Article, EditorialStatus, Poem, Tag
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work

pytestmark = pytest.mark.django_db

PREFIJO = "zz-largo-"


def _sembrar(*argumentos):
    call_command("seed_textos_largos", "--force", *argumentos, verbosity=0)


def _textos():
    return Article.objects.filter(slug__startswith=PREFIJO)


def _poemas():
    return Poem.objects.filter(slug__startswith=PREFIJO)


def test_siembra_seis_textos_y_cinco_poemas_publicados():
    _sembrar()
    assert _textos().count() == 6 and _poemas().count() == 5
    estados = {
        *_textos().values_list("status", flat=True),
        *_poemas().values_list("status", flat=True),
    }
    assert estados == {EditorialStatus.PUBLISHED}
    ensayo = _textos().get(slug=PREFIJO + "repetir-el-verso")
    assert ensayo.reading_time >= 15 and ensayo.authors.count() == 2
    critica = _textos().get(slug=PREFIJO + "contra-la-lectura-apurada")
    assert len(critica.title) > 190
    assert critica.authors.count() == 4 and critica.tags.count() == 8
    assert _textos().get(slug=PREFIJO + "dos-libros-sobre-el-agua").reviewed_works.count() == 2
    assert (
        len(_poemas().get(slug=PREFIJO + "letania-para-una-casa-que-se-vende").body.splitlines())
        > 100
    )


def test_sembrar_dos_veces_no_duplica_y_borrar_se_lleva_todo_lo_que_creo():
    _sembrar()
    _sembrar()
    assert _textos().count() == 6 and _poemas().count() == 5
    _sembrar("--borrar")
    for modelo in (Article, Poem, Work, Publisher, BookAuthor, Tag, Contributor):
        assert not modelo.objects.filter(slug__startswith=PREFIJO).exists(), modelo.__name__


def test_firma_con_las_integrantes_que_hay_y_no_las_borra():
    """Sin integrantes, firma con invitadas que crea y después borra; con ellas, las usa."""
    Contributor.objects.create(slug="fernanda-soto", display_name="Fernanda Soto", is_member=True)
    _sembrar()
    resena = _textos().get(slug=PREFIJO + "la-casa-como-lengua-extranjera")
    assert [c.slug for c in resena.authors.all()] == ["fernanda-soto"]
    _sembrar("--borrar")
    assert Contributor.objects.filter(slug="fernanda-soto").exists(), "borró a una integrante"


@override_settings(DEBUG=False)
def test_no_siembra_en_produccion_sin_force():
    with pytest.raises(CommandError, match="producción"):
        call_command("seed_textos_largos", verbosity=0)
    assert not _textos().exists()


def test_cada_pieza_se_lee_y_un_titulo_larguisimo_baja_un_paso(client):
    """Las once páginas responden con su título. Pasadas las noventa letras, el título de la
    columna ancla lleva la marca que lo baja un paso: el de un poema de 125 letras ocupaba
    catorce líneas y partía palabras por la mitad."""
    _sembrar()
    for pieza in (*_textos(), *_poemas()):
        respuesta = client.get(pieza.get_absolute_url())
        assert respuesta.status_code == 200, pieza.slug
        titulo = BeautifulSoup(respuesta.content, "html.parser").select_one(".lectura-ancla h1")
        assert titulo.get_text() == pieza.title
        assert ("titulo-largo" in titulo.get("class", [])) == (len(pieza.title) > 90), pieza.slug
