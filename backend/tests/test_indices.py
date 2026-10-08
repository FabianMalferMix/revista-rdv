"""Cabecera de los índices, cejillas y títulos de pestaña (backlog UX, tickets 1.2 y 1.12).

Los once índices abrían con su nombre a 12 px en gris, el texto más pequeño de la
página. Ahora comparten una cabecera con cejilla de dato vivo, título y una frase.
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import ArticleType, EditorialStatus, Section
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db

PLANTILLAS = Path(__file__).resolve().parent.parent / "templates"

INDICES = [
    "content:poem_index",
    "content:text_archive",
    "content:collection_index",
    "people:member_index",
    "media:recording_index",
    "showcase:publication_index",
    "showcase:press_index",
    "showcase:partner_index",
    "agenda:agenda",
    "agenda:trayectoria",
    "agenda:gallery",
]


def _pub(make_article, **kw):
    return make_article(status=EditorialStatus.PUBLISHED, published_at=timezone.now(), **kw)


@pytest.mark.parametrize("nombre", INDICES)
def test_cada_indice_abre_con_la_cabecera_comun(client, nombre):
    html = client.get(reverse(nombre)).content.decode()
    cabecera = re.search(r'<header class="index-head">(.*?)</header>', html, re.S)
    assert cabecera, f"{nombre} no usa la cabecera de índice"
    assert re.search(r"<h1>[^<]+</h1>", cabecera.group(1)), f"{nombre}: la cabecera no trae su h1"
    assert 'class="dek"' in cabecera.group(1), f"{nombre}: falta la frase que dice qué hay aquí"
    assert "page-title" not in html, f"{nombre} conserva el título de 12 px"


def test_el_titulo_de_12px_no_vuelve():
    """Ni la clase en una plantilla ni la regla en la hoja de estilos."""
    css = (PLANTILLAS.parent / "static" / "css" / "site.css").read_text(encoding="utf-8")
    assert ".page-title" not in css
    con_clase = [p.name for p in PLANTILLAS.rglob("*.html") if "page-title" in p.read_text("utf-8")]
    assert not con_clase, f"plantillas con page-title: {con_clase}"


def test_la_cejilla_cuenta_lo_que_hay_y_concuerda_en_numero(client, make_article):
    _pub(make_article, slug="uno", title="Texto uno")
    html = client.get(reverse("content:text_archive")).content.decode()
    assert re.search(r'<p class="kicker">\s*1 texto\s*</p>', html), "con uno debe decir «1 texto»"

    _pub(make_article, slug="dos", title="Texto dos")
    html = client.get(reverse("content:text_archive")).content.decode()
    assert re.search(r'<p class="kicker">\s*2 textos\s*</p>', html)


def test_un_indice_vacio_no_anuncia_cero(client):
    html = client.get(reverse("content:poem_index")).content.decode()
    cabecera = re.search(r'<header class="index-head">(.*?)</header>', html, re.S).group(1)
    assert "kicker" not in cabecera, "«0 poemas» no informa de nada: la cejilla se omite"


# ── Cejilla de las tarjetas ───────────────────────────────────────────────


def _cejilla(html):
    bloque = re.search(r'<span class="kicker">(.*?)</span>', html, re.S).group(1)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", bloque)).strip()


def test_la_cejilla_no_repite_la_seccion_cuando_dice_lo_mismo_que_el_tipo(client, make_article):
    """«Reseñas · Reseña» repetía la palabra en cada tarjeta del archivo."""
    resenas = Section.objects.create(slug="resenas", name="Reseñas")
    articulo = _pub(make_article, slug="r1", section=resenas, type=ArticleType.RESENA)
    assert articulo.seccion_aporta is False

    html = client.get(reverse("content:text_archive")).content.decode()
    assert _cejilla(html) == "Reseña"
    # La sección no se pierde: el tipo enlaza a ella.
    assert reverse("content:section_detail", args=["resenas"]) in html


def test_la_cejilla_nombra_la_seccion_cuando_anade_algo(client, make_article):
    cronica = Section.objects.create(slug="cronica", name="Crónica")
    articulo = _pub(make_article, slug="e1", section=cronica, type=ArticleType.ENTREVISTA)
    assert articulo.seccion_aporta is True
    assert _cejilla(client.get(reverse("content:text_archive")).content.decode()) == (
        "Crónica · Entrevista"
    )


def test_sin_seccion_la_cejilla_es_solo_el_tipo(client, make_article):
    articulo = _pub(make_article, slug="s1", section=None, type=ArticleType.ENSAYO)
    assert articulo.seccion_aporta is False
    assert _cejilla(client.get(reverse("content:text_archive")).content.decode()) == "Ensayo"


# ── Títulos de pestaña ────────────────────────────────────────────────────


def test_ningun_titulo_de_pestana_lleva_el_nombre_del_proyecto_anterior():
    """Diez plantillas cerraban el <title> con «— Reseñas» escrito a fuego: la pestaña de
    un artículo decía el nombre del proyecto del que este sitio heredó el código."""
    fijos = []
    for plantilla in PLANTILLAS.rglob("*.html"):
        for linea in plantilla.read_text(encoding="utf-8").splitlines():
            if "{% block title %}" in linea and "Reseñas" in linea.replace('default:"Reseñas"', ""):
                fijos.append(plantilla.name)
    assert not fijos, f"títulos con el nombre fijo: {fijos}"


def test_el_titulo_de_un_articulo_termina_en_el_nombre_del_sitio(client, make_article):
    perfil = SiteProfile.load()
    perfil.name = "Repitentes del Verso"
    perfil.save()
    _pub(make_article, slug="t1", title="Un texto")
    html = client.get(reverse("content:article_detail", args=["t1"])).content.decode()
    assert "<title>Un texto — Repitentes del Verso</title>" in html


# ── Qué páginas usan el carril ancho (backlog UX, ticket 2.1) ──────────────

LISTADOS_ANCHOS = INDICES + ["content:home", "content:search"]


@pytest.mark.parametrize("nombre", LISTADOS_ANCHOS)
def test_la_portada_y_los_indices_usan_el_carril_ancho(client, nombre):
    html = client.get(reverse(nombre)).content.decode()
    assert re.search(r'<main id="main" class="lienzo lienzo--ancho">', html), (
        f"{nombre} sigue en el carril de lectura"
    )


def test_las_paginas_de_lectura_se_quedan_en_su_carril(client, make_article, make_poem):
    """Un artículo o un poema no se ensanchan: se leen en una columna."""
    _pub(make_article, slug="lectura", title="Para leer")
    make_poem(slug="verso", status=EditorialStatus.PUBLISHED, published_at=timezone.now())
    for url in (
        reverse("content:article_detail", args=["lectura"]),
        reverse("content:poem_detail", args=["verso"]),
        reverse("submissions:submit"),
        reverse("showcase:dossier"),
    ):
        html = client.get(url).content.decode()
        clase = re.search(r'<main id="main" class="([^"]*)">', html).group(1).split()
        assert clase == ["lienzo"], f"{url}: <main> lleva {clase}"


def test_el_contenido_de_las_bandas_de_la_portada_vuelve_al_carril_ancho(client, make_article):
    """Una banda va de borde a borde; lo que lleva dentro, no."""
    from tests.factories import make_publication

    make_publication(slug="en-banda", title="Libro en banda", featured=True)
    html = client.get(reverse("content:home")).content.decode()
    bandas = re.findall(r'<section class="home-block band[^"]*">(.*?)</section>', html, re.S)
    assert bandas, "la portada ya no tiene bandas"
    for banda in bandas:
        assert 'class="band-in"' in banda, "una banda perdió su contenedor interior"
