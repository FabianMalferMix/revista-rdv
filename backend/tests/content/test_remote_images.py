"""Las imágenes de otro sitio que se pegan en un texto o en una página se copian a Recursos al
guardar desde el panel, y el cuerpo pasa a mostrar la copia.

Así ninguna página pública le pide una imagen a otro sitio: la CSP no la dejaría ver, y pedirla le
contaría a ese sitio cada visita. La que no se puede copiar se quita del cuerpo y el panel dice por
qué, sin impedir el guardado. Recursos dice qué cuerpo muestra cada imagen de la biblioteca y no
deja borrar la que uno muestra. La descarga misma (las direcciones internas, los tamaños, los
plazos) se prueba en tests/config/test_remote_fetch.py.
"""

import logging
import re
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import connection
from django.urls import reverse
from PIL import Image, ImageOps

from apps.content import services
from apps.content.models import Page
from apps.media.models import MediaAsset
from tests.factories import admin_form_fields, image_bytes, make_article, make_image, publish, soup
from tests.remote_sites import drip, response

pytestmark = pytest.mark.django_db

SITE = "https://repitentes.example"
FOTO = "https://fotos.example/ensayo.jpg"
# Cada aviso del panel, con su clase: la que le da el color (verde, amarillo).
COPIED = ("success", "Se copió una imagen de otro sitio a Recursos: el cuerpo ya muestra la copia.")
# Una imagen que no termina de llegar.
SLOW = b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n\r\n"
CADDYFILE = settings.BASE_DIR.parent / "infra" / "caddy" / "Caddyfile"


@pytest.fixture(autouse=True)
def _site_url(settings):
    settings.SITE_URL = SITE


def _jpeg(**kwargs):
    return response(image_bytes(**kwargs), headers={"Content-Type": "image/jpeg"})


def _not_copied(host, reason):
    return ("warning", f"No se copió la imagen de {host} ({reason}): se quitó del cuerpo.")


def _save(client, user, item, body, **fields):
    """Guarda `item` desde su ficha del panel, como `user`, con `body` como cuerpo. Devuelve los
    avisos del panel como (clase, texto), sin el último, el de Django que confirma el guardado."""
    meta = item._meta
    url = reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[item.pk])
    client.force_login(user)
    data = admin_form_fields(client.get(url).content, f"{meta.model_name}_form")
    data.update(body=body, **fields)
    answer = client.post(url, data, follow=True)
    assert answer.redirect_chain, "no se guardó: el formulario volvió con errores"
    page = BeautifulSoup(answer.content, "html.parser")
    notices = [
        (" ".join(li.get("class", [])), li.get_text(" ", strip=True))
        for li in page.select("ul.messagelist li")
    ]
    assert notices[-1][1].endswith("se cambió correctamente."), notices
    item.refresh_from_db()
    return notices[:-1]


def _images(html):
    return [(img.get("src"), img.get("alt")) for img in BeautifulSoup(html, "html.parser")("img")]


def _used_in(client):
    """La columna «Usado en» del listado de Recursos, por imagen."""
    page = soup(client, reverse("admin:media_mediaasset_changelist"))
    return {
        row.select_one(".field-__str__").get_text(strip=True): row.select_one(
            ".field-used_in"
        ).get_text(strip=True)
        for row in page.select("#result_list tbody tr")
    }


def test_an_image_from_another_site_is_copied_and_the_body_shows_the_copy(
    client, editor, remote_sites
):
    photo = image_bytes(gps=True)
    assert 0x8825 in Image.open(BytesIO(photo)).getexif(), "control: la foto dice dónde se tomó"
    remote_sites.serve(FOTO, response(photo, headers={"Content-Type": "image/jpeg"}))
    article = make_article(slug="ensayo", title="El ensayo", owner=editor)

    notices = _save(
        client,
        editor,
        article,
        f'<p>Antes.</p><figure><img src="{FOTO}" srcset="https://fotos.example/ensayo-2x.jpg 2x" '
        'alt="Foto del ensayo"></figure>',
    )

    assert notices == [COPIED]
    (copy,) = MediaAsset.objects.all()
    assert (copy.alt_text, copy.uploaded_by) == ("Foto del ensayo", editor)
    with copy.file.open("rb") as fh:
        assert not Image.open(fh).getexif()
    assert _images(article.body) == [(copy.file.url, "Foto del ensayo")]
    assert "fotos.example" not in article.body
    assert [target for _, target, _ in remote_sites.requests] == ["/ensayo.jpg"]
    assert _used_in(client) == {"Foto del ensayo": "cuerpo de artículo"}

    publish(article)
    page = client.get(article.get_absolute_url())
    assert page.status_code == 200
    assert "fotos.example" not in page.content.decode()
    body = BeautifulSoup(page.content, "html.parser").select_one("div.body")
    assert [img["src"] for img in body("img")] == [copy.file.url]


@pytest.mark.parametrize(
    ("fmt", "content_type", "extension"),
    [
        ("JPEG", "image/jpeg", "jpeg"),
        ("PNG", "image/png", "png"),
        ("WEBP", "image/webp", "webp"),
        ("PNG", "image/jpeg", "png"),
    ],
    ids=["jpeg", "png", "webp", "png-que-dice-jpeg"],
)
def test_the_copy_is_named_after_what_the_image_is(
    client, editor, remote_sites, fmt, content_type, extension
):
    """Caddy sirve cada archivo con el tipo que dice su extensión: la de la copia es la del formato
    de la imagen, no la que dijo el otro sitio."""
    remote_sites.serve(FOTO, response(image_bytes(fmt), headers={"Content-Type": content_type}))
    article = make_article(owner=editor)

    assert _save(client, editor, article, f'<img src="{FOTO}" alt="Foto del ensayo">') == [COPIED]

    (copy,) = MediaAsset.objects.all()
    assert PurePosixPath(copy.file.name).name == f"foto-del-ensayo.{extension}"
    with copy.file.open("rb") as fh:
        assert Image.open(fh).format == fmt


@pytest.mark.parametrize(
    ("alt", "alt_text", "name"),
    [
        ("", "Imagen copiada de fotos.example", "imagen-copiada-de-fotosexample.jpeg"),
        ("写真", "写真", "imagen-copiada.jpeg"),
        (
            "palabra " * 40,
            ("palabra " * 40)[:255],
            "palabra-palabra-palabra-palabra-palabra-palabra-pa.jpeg",
        ),
    ],
    ids=["sin-texto", "sin-letras-latinas", "largo"],
)
def test_the_copy_takes_its_text_and_its_name_from_the_image_alt(
    client, editor, remote_sites, alt, alt_text, name
):
    """Sin texto alternativo, la copia dice de dónde vino; con uno más largo de lo que cabe en
    Recursos, lleva lo que cabe. El nombre del archivo sale de ese texto."""
    remote_sites.serve(FOTO, _jpeg())
    article = make_article(owner=editor)

    assert _save(client, editor, article, f'<img src="{FOTO}" alt="{alt}">') == [COPIED]

    (copy,) = MediaAsset.objects.all()
    assert copy.alt_text == alt_text
    assert PurePosixPath(copy.file.name).name == name
    assert [src for src, _ in _images(article.body)] == [copy.file.url]


def _huge_png():
    """Un PNG de 64 megapíxeles que pesa poco: blanco y negro, de un solo color."""
    buffer = BytesIO()
    Image.new("1", (8000, 8000)).save(buffer, format="PNG")
    return response(buffer.getvalue())


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (
            lambda: response(image_bytes("GIF"), headers={"Content-Type": "image/gif"}),
            "no es JPEG, PNG ni WebP",
        ),
        (_huge_png, "pasa de 40 megapíxeles"),
        (
            lambda: response(b"<p>Hola</p>", headers={"Content-Type": "text/html"}),
            "no es una imagen",
        ),
        (
            lambda: response(b"No existe.", "404 Not Found", {"Content-Type": "text/plain"}),
            "respondió con el código 404",
        ),
        (
            lambda: response(b"no soy una imagen", headers={"Content-Type": "image/jpeg"}),
            "no se pudo leer como imagen",
        ),
        (None, "el nombre del sitio no existe"),
    ],
    ids=["gif", "enorme", "pagina", "no-existe", "rota", "sitio-que-no-existe"],
)
def test_an_image_that_cannot_be_copied_leaves_the_body_and_the_save_goes_on(
    client, editor, remote_sites, answer, reason
):
    if answer is not None:
        remote_sites.serve(FOTO, answer())
    article = make_article(title="Antes", owner=editor)
    body = (
        "<p>Una foto del ensayo.</p>"
        f'<figure><img src="{FOTO}" srcset="https://fotos.example/ensayo-2x.jpg 2x" '
        'alt="Foto de fuera"></figure>'
        '<figure><img src="/media/assets/ensayo.jpg" alt="Foto del sitio">'
        "<figcaption>Ensayo.</figcaption></figure>"
    )

    notices = _save(client, editor, article, body, title="Después")

    assert notices == [_not_copied("fotos.example", reason)]
    assert article.title == "Después"
    assert _images(article.body) == [("/media/assets/ensayo.jpg", "Foto del sitio")]
    assert len(BeautifulSoup(article.body, "html.parser")("figure")) == 1
    assert "fotos.example" not in article.body
    assert not MediaAsset.objects.exists()


def test_each_image_is_copied_once_and_each_one_that_is_not_is_told(client, editor, remote_sites):
    remote_sites.serve(FOTO, _jpeg())
    remote_sites.serve(
        "https://otro.example/rota.png",
        response(b"No existe.", "404 Not Found", {"Content-Type": "text/plain"}),
    )
    remote_sites.serve("https://otro.example/buena.png", response(image_bytes("PNG")))
    article = make_article(owner=editor)
    body = (
        f'<p><img src="{FOTO}" alt="Foto del ensayo"></p>'
        '<p><img src="https://otro.example/rota.png" alt="Rota"></p>'
        '<p><img src="/media/assets/propia.jpg" alt="Propia"></p>'
        '<p><img src="https://otro.example/buena.png" alt="Buena"></p>'
        f'<p><img src="{FOTO}" alt="Otra vez"></p>'
    )

    notices = _save(client, editor, article, body)

    assert notices == [
        (
            "success",
            "Se copiaron 2 imágenes de otros sitios a Recursos: el cuerpo ya muestra las copias.",
        ),
        _not_copied("otro.example", "respondió con el código 404"),
    ]
    copies = {asset.alt_text: asset.file.url for asset in MediaAsset.objects.all()}
    assert _images(article.body) == [
        (copies["Foto del ensayo"], "Foto del ensayo"),
        ("/media/assets/propia.jpg", "Propia"),
        (copies["Buena"], "Buena"),
        (copies["Foto del ensayo"], "Otra vez"),
    ]
    assert [target for _, target, _ in remote_sites.requests] == [
        "/ensayo.jpg",
        "/rota.png",
        "/buena.png",
    ]


def test_an_author_copies_the_images_of_their_own_text(client, autor, remote_sites):
    remote_sites.serve(FOTO, _jpeg())
    article = make_article(owner=autor)

    assert _save(client, autor, article, f'<img src="{FOTO}" alt="Foto del ensayo">') == [COPIED]

    (copy,) = MediaAsset.objects.all()
    assert copy.uploaded_by == autor
    assert _images(article.body) == [(copy.file.url, "Foto del ensayo")]


def test_who_cannot_upload_images_copies_none(client, editor, groups, remote_sites):
    groups["editor"].permissions.remove(Permission.objects.get(codename="add_mediaasset"))
    remote_sites.serve(FOTO, _jpeg())  # el sitio contesta: si se le pidiera, habría copia
    article = make_article(owner=editor)

    notices = _save(client, editor, article, f'<p>Texto.</p><p><img src="{FOTO}" alt="Foto"></p>')

    assert notices == [_not_copied("fotos.example", "no tienes permiso para subir imágenes")]
    assert remote_sites.lookups == []
    assert not MediaAsset.objects.exists()
    assert _images(article.body) == [] and "<p>Texto.</p>" in article.body


@pytest.mark.parametrize(
    ("written", "asked"),
    [
        (
            "https://fotos.example/ensayo.jpg?ancho=800&amp;calidad=80",
            "/ensayo.jpg?ancho=800&calidad=80",
        ),
        ("//fotos.example/ensayo.jpg", "/ensayo.jpg"),
        ("https:\\\\fotos.example\\ensayo.jpg", "/ensayo.jpg"),
    ],
    ids=["entidad", "sin-esquema", "barras-invertidas"],
)
def test_the_image_is_asked_where_the_browser_would_ask_for_it(
    client, editor, remote_sites, written, asked
):
    remote_sites.serve(f"https://fotos.example{asked}", _jpeg())
    article = make_article(owner=editor)

    assert _save(client, editor, article, f'<img src="{written}" alt="Foto">') == [COPIED]

    assert [target for _, target, _ in remote_sites.requests] == [asked]
    (copy,) = MediaAsset.objects.all()
    assert _images(article.body) == [(copy.file.url, "Foto")]


def test_the_notices_and_the_log_name_only_the_site_of_an_image(
    client, editor, remote_sites, caplog
):
    """La dirección entera puede llevar algo que solo debía conocer quien la tenía, como la clave
    de un enlace privado: el aviso y el registro dicen solo el sitio."""
    address = "https://fotos.example/ensayo.jpg?clave=s3creto"
    remote_sites.serve(address, response(b"", "403 Forbidden", {"Content-Type": "text/plain"}))
    article = make_article(owner=editor)

    notices = _save(client, editor, article, f'<img src="{address}" alt="Foto">')

    assert [target for _, target, _ in remote_sites.requests] == ["/ensayo.jpg?clave=s3creto"]
    assert notices == [_not_copied("fotos.example", "respondió con el código 403")]
    assert (
        "apps.content.services",
        logging.WARNING,
        "No se copió una imagen de fotos.example: respondió con el código 403",
    ) in caplog.record_tuples
    assert "s3creto" not in caplog.text and "s3creto" not in article.body


def test_an_unexpected_failure_copying_an_image_is_logged_and_the_save_goes_on(
    client, editor, monkeypatch, caplog
):
    """Un error de la base a mitad de una copia no deja la transacción del guardado rota."""

    def broken(url, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM tabla_que_no_existe")

    monkeypatch.setattr(services, "copy_remote_image", broken)
    article = make_article(title="Antes", owner=editor)

    notices = _save(
        client, editor, article, f'<p>Texto.</p><img src="{FOTO}" alt="Foto">', title="Después"
    )

    assert notices == [
        _not_copied("fotos.example", "un error inesperado, que quedó en el registro")
    ]
    assert article.title == "Después" and _images(article.body) == []
    (record,) = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert record.getMessage() == "Falló la copia de una imagen de fotos.example"
    assert record.exc_info


def test_a_photo_that_cannot_be_cleaned_of_its_metadata_is_not_copied(
    client, editor, remote_sites, monkeypatch
):
    """Se publicaría con el lugar donde se tomó: no queda ni en Recursos ni en el disco."""

    def broken(image):
        raise OSError("No queda espacio en el disco")

    monkeypatch.setattr(ImageOps, "exif_transpose", broken)
    remote_sites.serve(FOTO, _jpeg(gps=True))
    article = make_article(owner=editor)

    notices = _save(
        client, editor, article, f'<p>Texto.</p><img src="{FOTO}" alt="Foto del ensayo">'
    )

    assert [target for _, target, _ in remote_sites.requests] == ["/ensayo.jpg"]  # control
    assert notices == [_not_copied("fotos.example", "no se pudo limpiar de metadatos")]
    assert not MediaAsset.objects.exists()
    assert not [path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()]
    assert _images(article.body) == []


SLOW_THEN_GOOD = (
    '<p><img src="https://lento.example/foto.png" alt="Lenta"></p>'
    f'<p><img src="{FOTO}" alt="Foto del ensayo"></p>'
)


def test_a_site_that_takes_too_long_loses_its_image_and_not_the_others(
    client, editor, remote_sites, monkeypatch
):
    monkeypatch.setattr(services, "IMAGE_SECONDS", 0.3)
    remote_sites.serve("https://lento.example/foto.png", drip(SLOW))
    remote_sites.serve(FOTO, _jpeg())
    article = make_article(owner=editor)

    notices = _save(client, editor, article, SLOW_THEN_GOOD)

    assert notices == [COPIED, _not_copied("lento.example", "tardó demasiado")]
    (copy,) = MediaAsset.objects.all()
    assert _images(article.body) == [(copy.file.url, "Foto del ensayo")]


def test_a_save_stops_asking_other_sites_when_its_time_is_up(
    client, editor, remote_sites, monkeypatch
):
    monkeypatch.setattr(services, "SAVE_SECONDS", 0.3)
    remote_sites.serve("https://lento.example/foto.png", drip(SLOW))
    remote_sites.serve(FOTO, _jpeg())
    article = make_article(title="Antes", owner=editor)

    notices = _save(client, editor, article, SLOW_THEN_GOOD, title="Después")

    assert notices == [
        _not_copied("lento.example", "tardó demasiado"),
        _not_copied("fotos.example", "no quedó tiempo para copiarla"),
    ]
    assert remote_sites.lookups == ["lento.example"]
    assert article.title == "Después" and _images(article.body) == []


def test_a_save_ends_before_caddy_stops_waiting_for_it():
    """Caddy corta la respuesta que tarda más de su `write`: el guardado deja de pedir imágenes
    antes, con margen para lo demás (guardar el texto, limpiar la última copia)."""
    if not CADDYFILE.is_file():
        pytest.skip("el Caddyfile no está en este árbol")
    write = int(re.search(r"\bwrite (\d+)s\b", CADDYFILE.read_text()).group(1))
    assert services.IMAGE_SECONDS <= services.SAVE_SECONDS <= write / 2


@pytest.mark.parametrize(
    "shown",
    [
        lambda image: image.file.url,
        lambda image: SITE + image.file.url,
        lambda image: "../../../.." + image.file.url,
        lambda image: settings.MEDIA_URL + image._derivative_name(480),
        lambda image: settings.MEDIA_URL + image._portada_name(960, "avif"),
    ],
    ids=["ruta", "absoluta", "relativa", "copia-del-srcset", "copia-de-la-portada"],
)
def test_resources_says_which_body_shows_each_image(client, editor, shown):
    """Como la nombre el cuerpo: por su ruta, por la dirección entera, relativa a la ficha (como la
    deja el editor del panel) o por una de sus copias a otro tamaño. La «ñ» va escapada en la
    dirección del archivo y tal cual en su nombre."""
    image = make_image("ensayo-de-año", alt="Foto del ensayo")
    assert quote("ñ") in image.file.url, "control: la dirección escapa la «ñ»"
    make_image("suelta", alt="Imagen que nada usa")
    make_article(body=f'<p><img src="{shown(image)}" alt="Foto"></p>')
    client.force_login(editor)

    assert _used_in(client) == {
        "Foto del ensayo": "cuerpo de artículo",
        "Imagen que nada usa": "—",
    }


def test_an_image_a_body_shows_is_deleted_only_once_the_body_drops_it(client, editor):
    image = make_image("ensayo", alt="Foto del ensayo")
    article = make_article(
        title="Cartografía del eco",
        body=f'<p>Texto.</p><p><img src="{image.file.url}" alt="Foto"></p>',
        owner=editor,
    )
    url = reverse("admin:media_mediaasset_delete", args=[image.pk])
    client.force_login(editor)

    confirmation = soup(client, url)
    assert "Cartografía del eco" in confirmation.select_one("#deleted-objects").get_text()
    assert "no se puede borrar" in confirmation.select_one("#content").get_text()
    client.post(url, {"post": "yes"})
    assert MediaAsset.objects.filter(pk=image.pk).exists()

    assert _save(client, editor, article, "<p>Texto.</p>") == []
    client.post(url, {"post": "yes"})
    assert not MediaAsset.objects.filter(pk=image.pk).exists()


def test_a_page_copies_its_images_too(client, editor, remote_sites):
    remote_sites.serve(FOTO, _jpeg())
    page = Page.objects.create(slug="con-fotos", title="Con fotos", body="<p>x</p>")

    assert _save(client, editor, page, f'<img src="{FOTO}" alt="Foto del ensayo">') == [COPIED]

    (copy,) = MediaAsset.objects.all()
    assert _images(page.body) == [(copy.file.url, "Foto del ensayo")]
    assert _used_in(client) == {"Foto del ensayo": "cuerpo de página"}
