"""Sala de lectura, fichas a dos columnas y pie de entidad (backlog UX, ticket 2.4).

Poema y artículo se leen en una sala con su columna ancla; integrante, publicación y
evento ponen su imagen al lado de lo que son; y cada ficha termina en salidas hacia el
índice, quien firma y lo que viene antes y después. Antes eran callejones sin salida:
una ficha de poema tenía un solo enlace interno.
"""

from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import SafeString

from apps.content.models import (
    ArticleContributor,
    Collection,
    CollectionPoem,
    EditorialStatus,
    Poem,
    PoemContributor,
    PublishStatus,
)
from apps.content.pie import vecinos, vecinos_en_lista
from apps.content.templatetags.versos import versos
from apps.people.models import Contributor
from tests.factories import make_event, make_publication, make_recording

pytestmark = pytest.mark.django_db


def _sopa(client, url):
    respuesta = client.get(url)
    assert respuesta.status_code == 200
    return BeautifulSoup(respuesta.content, "html.parser")


def _poema(slug, dias=0, **kw):
    kw.setdefault("title", slug.capitalize())
    kw.setdefault("body", "Un verso")
    return Poem.objects.create(
        slug=slug,
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now() - timedelta(days=dias),
        **kw,
    )


def _retrato(nombre):
    """Un MediaAsset con imagen, para que cargar retratos cueste consultas de verdad."""
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image

    from apps.media.models import MediaAsset

    buf = BytesIO()
    Image.new("RGB", (40, 50), (20, 30, 40)).save(buf, format="JPEG")
    asset = MediaAsset(alt_text=f"Retrato de {nombre}")
    asset.file.save(f"{nombre}.jpg", ContentFile(buf.getvalue()))
    return asset


def _salidas(sopa):
    pie = sopa.select_one("nav.pie-entidad")
    assert pie is not None, "la ficha no tiene pie de entidad"
    return {
        li.select_one(".rotulo").get_text(): (li.a.get_text(), li.a["href"])
        for li in pie.select("li")
    }


# ── El filtro de versos ───────────────────────────────────────────────────


def test_versos_marca_cada_linea_y_agrupa_las_estrofas():
    html = versos("Verso uno\n    verso con sangría\n\nVerso final")
    assert html == (
        '<p class="estrofa"><span class="verso">Verso uno</span>'
        '<span class="verso">    verso con sangría</span></p>'
        '<p class="estrofa"><span class="verso">Verso final</span></p>'
    )
    assert isinstance(html, SafeString)


def test_versos_escapa_cada_linea_antes_de_envolverla():
    """El cuerpo lo escribe una persona: el filtro devuelve HTML seguro solo porque cada
    verso se escapa primero."""
    html = versos('<script>alert("x")</script>\n<b>negrita</b>')
    assert "<script>" not in html and "<b>" not in html
    assert "&lt;script&gt;" in html and "&lt;b&gt;negrita&lt;/b&gt;" in html


@pytest.mark.parametrize(
    "cuerpo,estrofas",
    [
        ("\n\nuno\n\n\n\ndos\n\n", 2),  # varias líneas en blanco: un solo salto
        ("uno\n   \ndos", 2),  # una línea con solo espacios también separa
        ("uno\ndos\ntres", 1),
        ("", 0),
        (None, 0),
    ],
)
def test_versos_cuenta_las_estrofas(cuerpo, estrofas):
    assert str(versos(cuerpo)).count('<p class="estrofa">') == estrofas


# ── Sala de lectura ───────────────────────────────────────────────────────


def test_el_poema_se_lee_verso_a_verso_en_su_sala(client):
    autora = Contributor.objects.create(slug="autora", display_name="La Autora", is_member=True)
    poema = _poema(
        "sala", body="Verso uno\n    verso con sangría\n\nVerso final", epigraph="a quien lee"
    )
    PoemContributor.objects.create(poem=poema, contributor=autora)

    sopa = _sopa(client, poema.get_absolute_url())
    sala = sopa.select_one("article.lectura")
    ancla, cuerpo = sala.select_one(".lectura-ancla"), sala.select_one(".lectura-cuerpo")
    assert ancla.h1.get_text() == "Sala"
    assert ancla.select_one(".poem-epigraph").get_text() == "a quien lee"
    assert ancla.select_one(".lectura-firmas a")["href"] == autora.get_absolute_url()
    versos_html = cuerpo.select(".poem-body .estrofa .verso")
    assert [v.get_text() for v in versos_html] == [
        "Verso uno",
        "    verso con sangría",
        "Verso final",
    ]
    assert len(cuerpo.select(".poem-body .estrofa")) == 2


def test_el_registro_del_poema_lleva_a_su_ficha_y_no_al_tercero(client):
    """El enlace iba directo a YouTube, saltándose el aviso de privacidad de la ficha del
    registro. Ahora lleva a la ficha; un archivo propio se escucha ahí mismo."""
    registro = make_recording(slug="lectura", title="Lectura", embed_url="https://vimeo.com/123")
    poema = _poema("con-registro", recording=registro)
    sopa = _sopa(client, poema.get_absolute_url())
    bloque = sopa.select_one(".lectura-ancla .lectura-registro")
    assert bloque.select_one("a")["href"] == registro.get_absolute_url()
    assert "vimeo.com" not in str(sopa)
    assert bloque.select_one("audio") is None, "un video no se reproduce en la ficha del poema"


def test_el_articulo_ensena_su_imagen_y_la_obra_resenada_en_la_sala(client, make_article):
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image

    from apps.media.models import MediaAsset

    buf = BytesIO()
    Image.new("RGB", (60, 40), (10, 20, 30)).save(buf, format="JPEG")
    imagen = MediaAsset(alt_text="Imagen del texto", credit="Foto: Alguien")
    imagen.file.save("texto.jpg", ContentFile(buf.getvalue()))
    articulo = make_article(
        slug="con-imagen",
        title="Con imagen",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
        cover_image=imagen,
    )
    sopa = _sopa(client, articulo.get_absolute_url())
    figura = sopa.select_one(".lectura-cuerpo figure.lectura-imagen")
    assert figura.img["alt"] == "Imagen del texto"
    assert figura.figcaption.get_text(strip=True) == "Foto: Alguien"
    assert sopa.select_one(".lectura-ancla h1").get_text() == "Con imagen"
    assert sopa.select_one(".lectura-cuerpo .body") is not None


@pytest.mark.parametrize("tipo", ["poema", "articulo"])
def test_la_ancla_fija_no_comparte_contenedor_con_el_pie(client, make_article, tipo):
    """La ancla es `position:sticky`, y un elemento fijo se desplaza por todo su
    contenedor. Con el pie dentro de la misma rejilla, al llegar al final la ancla bajaba y
    se montaba sobre las salidas: 255 px en un artículo a 951 de ancho (lo vio el dueño del
    sitio). La sala va en su bloque y el pie, fuera."""
    if tipo == "poema":
        objeto = _poema("fijo")
    else:
        objeto = make_article(
            slug="fijo", status=EditorialStatus.PUBLISHED, published_at=timezone.now()
        )
    sopa = _sopa(client, objeto.get_absolute_url())
    ancla = sopa.select_one(".lectura-ancla")
    sala = ancla.parent
    assert "lectura-sala" in sala["class"], "la ancla debe vivir en la sala, no en el artículo"
    assert sala.select_one("nav.pie-entidad") is None, (
        "el pie no puede compartir contenedor con la ancla"
    )
    assert sala.find_next_sibling("nav", class_="pie-entidad") is not None


# ── Fichas ────────────────────────────────────────────────────────────────


def test_la_ficha_de_integrante_pone_el_retrato_al_lado(client):
    sin_retrato = Contributor.objects.create(
        slug="sin-retrato", display_name="Rocío Carrasco", is_member=True, active=True
    )
    sopa = _sopa(client, sin_retrato.get_absolute_url())
    cabecera = sopa.select_one(".ficha .ficha-cabecera")
    monograma = cabecera.select_one(".ficha-medio .ficha-retrato.ficha-monograma")
    assert monograma.get_text() == "RC" and monograma["aria-hidden"] == "true"
    assert cabecera.select_one(".ficha-texto h1").get_text() == "Rocío Carrasco"


def test_en_su_ficha_cada_fila_omite_su_propia_firma(client, make_article):
    """Cada fila de sus textos repetía su nombre. Un texto a cuatro manos sigue nombrando
    a la otra persona."""
    ella = Contributor.objects.create(slug="ella", display_name="Ella Misma", is_member=True)
    otra = Contributor.objects.create(slug="otra", display_name="La Otra")
    sola = make_article(slug="sola", status=EditorialStatus.PUBLISHED, published_at=timezone.now())
    juntas = make_article(
        slug="juntas", status=EditorialStatus.PUBLISHED, published_at=timezone.now()
    )
    ArticleContributor.objects.create(article=sola, contributor=ella)
    ArticleContributor.objects.create(article=juntas, contributor=ella, position=0)
    ArticleContributor.objects.create(article=juntas, contributor=otra, position=1)
    suyo = _poema("suyo")
    PoemContributor.objects.create(poem=suyo, contributor=ella)

    pies = {
        f.select_one(".fila-titulo a")["href"]: f.select_one(".fila-pie").get_text(" ", strip=True)
        for f in _sopa(client, ella.get_absolute_url()).select("li.fila")
    }
    assert "Ella Misma" not in pies[sola.get_absolute_url()]
    assert "La Otra" in pies[juntas.get_absolute_url()]
    assert "Ella Misma" not in pies[juntas.get_absolute_url()]
    assert "Ella Misma" not in pies[suyo.get_absolute_url()]
    # En el archivo general la firma sigue ahí.
    archivo = _sopa(client, reverse("content:text_archive")).get_text()
    assert "Ella Misma" in archivo


def test_la_ficha_de_publicacion_pone_la_cubierta_al_lado(client):
    publicacion = make_publication(slug="sin-tapa", title="Sin tapa")
    medio = _sopa(client, publicacion.get_absolute_url()).select_one(".ficha-cabecera .ficha-medio")
    assert medio.select_one(".ficha-cubierta.pub-cover-fallback").get_text(strip=True) == "Sin tapa"


def test_un_evento_sin_afiche_no_deja_una_columna_vacia(client):
    evento = make_event(slug="sin-afiche", title="Sin afiche")
    cabecera = _sopa(client, evento.get_absolute_url()).select_one(".ficha-cabecera")
    assert "ficha-cabecera--sin-medio" in cabecera["class"]
    assert cabecera.select_one(".ficha-medio") is None


# ── Pie de entidad ────────────────────────────────────────────────────────


def test_el_pie_del_poema_lleva_al_indice_a_quien_firma_a_su_coleccion_y_a_sus_vecinos(client):
    autora = Contributor.objects.create(slug="autora", display_name="La Autora", is_member=True)
    nuevo, medio, viejo = _poema("nuevo", 1), _poema("medio", 2), _poema("viejo", 3)
    PoemContributor.objects.create(poem=medio, contributor=autora)
    coleccion = Collection.objects.create(
        slug="col", title="La colección", status=PublishStatus.PUBLISHED
    )
    CollectionPoem.objects.create(collection=coleccion, poem=medio)

    salidas = _salidas(_sopa(client, medio.get_absolute_url()))
    assert salidas["Índice"] == ("Todos los poemas", reverse("content:poem_index"))
    assert salidas["Más de"] == ("La Autora", autora.get_absolute_url())
    assert salidas["En la colección"] == ("La colección", coleccion.get_absolute_url())
    # El índice va del más reciente al más antiguo: «siguiente» es el de después en la lista.
    assert salidas["Poema anterior"] == ("Nuevo", nuevo.get_absolute_url())
    assert salidas["Poema siguiente"] == ("Viejo", viejo.get_absolute_url())

    extremos = _salidas(_sopa(client, nuevo.get_absolute_url()))
    assert "Poema anterior" not in extremos and extremos["Poema siguiente"][0] == "Medio"


def test_una_coleccion_sin_publicar_no_sale_en_el_pie(client):
    poema = _poema("solo")
    borrador = Collection.objects.create(slug="b", title="Borrador", status=PublishStatus.DRAFT)
    CollectionPoem.objects.create(collection=borrador, poem=poema)
    assert "En la colección" not in _salidas(_sopa(client, poema.get_absolute_url()))


@pytest.mark.parametrize(
    "fabricar,esperadas",
    [
        (
            lambda: Contributor.objects.create(
                slug="i", display_name="I", is_member=True, active=True
            ),
            {"Índice", "El colectivo", "Para programar"},
        ),
        (lambda: make_publication(slug="p", title="P"), {"Índice", "Trayectoria"}),
        (
            lambda: make_event(slug="e", title="E", starts_at=timezone.now() - timedelta(days=3)),
            {"Trayectoria", "Para programar"},
        ),
        (lambda: make_recording(slug="r", title="R"), {"Índice"}),
    ],
)
def test_cada_ficha_termina_en_salidas(client, fabricar, esperadas):
    objeto = fabricar()
    salidas = _salidas(_sopa(client, objeto.get_absolute_url()))
    assert esperadas <= set(salidas), f"faltan salidas: {esperadas - set(salidas)}"
    for _, url in salidas.values():
        assert url.startswith("/"), "las salidas del pie son internas"


def test_el_registro_lleva_al_poema_que_registra(client):
    registro = make_recording(slug="reg", title="Reg")
    poema = _poema("registrado", recording=registro)
    salidas = _salidas(_sopa(client, registro.get_absolute_url()))
    assert salidas["Poema registrado"] == (poema.title, poema.get_absolute_url())


# ── Vecinos ───────────────────────────────────────────────────────────────


def test_vecinos_desempata_por_clave_las_piezas_de_la_misma_fecha():
    """Dos poemas publicados en el mismo instante no pueden saltarse el uno al otro."""
    instante = timezone.now()
    a = Poem.objects.create(
        slug="a", title="A", body="x", status=EditorialStatus.PUBLISHED, published_at=instante
    )
    b = Poem.objects.create(
        slug="b", title="B", body="x", status=EditorialStatus.PUBLISHED, published_at=instante
    )
    publicados = Poem.objects.filter(status=EditorialStatus.PUBLISHED)
    assert vecinos(publicados, a) == (b, None)
    assert vecinos(publicados, b) == (None, a)


def test_vecinos_sin_fecha_no_tiene_vecinos():
    poema = Poem.objects.create(slug="s", title="S", body="x", status=EditorialStatus.PUBLISHED)
    assert vecinos(Poem.objects.all(), poema) == (None, None)


def test_vecinos_en_lista_sigue_el_orden_del_indice():
    uno, dos, tres = (
        Contributor.objects.create(
            slug=f"m{i}", display_name=f"M{i}", is_member=True, active=True, position=i
        )
        for i in (1, 2, 3)
    )
    historica = Contributor.objects.create(slug="h", display_name="H", is_member=True, active=False)
    lista = Contributor.members()
    assert vecinos_en_lista(lista, dos) == (uno, tres)
    assert vecinos_en_lista(lista, uno) == (None, dos)
    assert vecinos_en_lista(lista, historica) == (None, None), "fuera de la lista no hay vecinos"


# ── Consultas ─────────────────────────────────────────────────────────────


def test_la_ficha_del_poema_no_crece_en_consultas_con_sus_autoras(
    client, django_assert_max_num_queries
):
    poema = _poema("varias")
    for i in range(5):
        persona = Contributor.objects.create(
            slug=f"p{i}", display_name=f"P{i}", is_member=True, photo=_retrato(f"p{i}")
        )
        PoemContributor.objects.create(poem=poema, contributor=persona)
    client.get(poema.get_absolute_url())
    with django_assert_max_num_queries(12):
        assert client.get(poema.get_absolute_url()).status_code == 200


def test_la_ficha_de_integrante_no_crece_con_su_obra(
    client, django_assert_max_num_queries, make_article
):
    ella = Contributor.objects.create(
        slug="obra", display_name="Con Obra", is_member=True, active=True
    )
    for i in range(10):
        # Cada poema con su registro: la fila pregunta si está publicado.
        registro = make_recording(slug=f"r{i}", title=f"R{i}")
        PoemContributor.objects.create(
            poem=_poema(f"p{i}", i, recording=registro), contributor=ella
        )
        texto = make_article(
            slug=f"t{i}", status=EditorialStatus.PUBLISHED, published_at=timezone.now()
        )
        ArticleContributor.objects.create(article=texto, contributor=ella)
    client.get(ella.get_absolute_url())
    with django_assert_max_num_queries(18):
        assert client.get(ella.get_absolute_url()).status_code == 200
