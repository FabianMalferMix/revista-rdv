"""`seed_material_generico` dibuja marcadores con proporciones reales y los asigna sin
pisar material real. Como todos los comandos de desarrollo, solo corre con DEBUG y fuera de
producción (tests/test_dev_tools.py).

Las pruebas de asignación sustituyen los dibujantes por imágenes diminutas: lo que se
verifica es la lógica (asignación e idempotencia), no el dibujo. El dibujo se
prueba aparte, una vez por tipo, comprobando solo el tamaño del lienzo.
"""

from io import BytesIO
from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from PIL import Image

from apps.agenda.models import Event
from apps.content.models import ArticleType
from apps.devtools import identity
from apps.devtools.management.commands import seed_material_generico as cmd
from apps.devtools.placeholders import PLACEHOLDER_CREDIT, is_placeholder
from apps.media.models import MediaAsset, Recording
from apps.people.models import Contributor
from apps.reviews.models import Work
from apps.showcase.models import Partner, PressMention, Publication, SiteProfile
from tests.factories import (
    make_event,
    make_photo,
    make_publication,
    make_published_article,
    make_recording,
)

pytestmark = pytest.mark.django_db


def _png_diminuto():
    buf = BytesIO()
    Image.new("RGB", (8, 10), (200, 20, 100)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def dibujantes_diminutos(monkeypatch):
    """Cada generador devuelve una imagen de 8×10: la prueba no paga el dibujo real."""

    def stub(*args, **kwargs):
        return Image.new("RGB", (8, 10), (31, 115, 199)), "PNG"

    for nombre in (
        "_retrato",
        "_foto_lectura",
        "_afiche",
        "_cubierta",
        "_caratula_registro",
        "_logo",
        "_imagen_texto",
        "_foto_grupo",
    ):
        monkeypatch.setattr(cmd, nombre, stub)


def _credited(photo, credit):
    photo.asset.credit = credit
    photo.asset.save(update_fields=["credit"])
    return photo


@pytest.fixture
def unillustrated_content():
    """Un poco de cada cosa que lleva imagen, sin ninguna: dos integrantes, dos actividades (una
    con tres fotos del colectivo), dos publicaciones, un registro, un aliado, una mención en
    prensa, un texto y una obra reseñada."""
    for slug, name in (("fernanda-soto", "Fernanda Soto"), ("paula-miranda", "Paula Miranda")):
        Contributor.objects.create(slug=slug, display_name=name, is_member=True, active=True)
    with_photos = make_event(slug="recital-con-fotos", title="Recital con fotos")
    for position in range(3):
        _credited(make_photo(with_photos, position), "Archivo del colectivo")
    make_event(slug="taller-sin-fotos", title="Taller sin fotos")
    make_publication(slug="plaquette", title="Plaquette")
    make_publication(slug="fanzine", title="Fanzine")
    make_recording(slug="recital-grabado", title="Recital grabado")
    Partner.objects.create(name="Fondo Imaginario de las Letras", kind=Partner.Kind.FINANCIAMIENTO)
    PressMention.objects.create(
        title="Nota de prueba", outlet="Gaceta de Prueba", kind=PressMention.Kind.NOTA
    )
    make_published_article(slug="resena", title="Una reseña", type=ArticleType.RESENA)
    Work.objects.create(slug="libro-resenado", title="Libro reseñado", kind=Work.Kind.LIBRO)


def test_asigna_marcadores_sin_pisar_material_real_y_es_idempotente(
    settings, tmp_path, dibujantes_diminutos, unillustrated_content
):
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path

    # Material REAL simulado: una integrante con retrato cuyo crédito no es de marcador.
    real = MediaAsset(alt_text="Retrato de Fernanda Soto", credit="Foto: Alguien Real")
    real.file.save("real.png", ContentFile(_png_diminuto()), save=True)
    fernanda = Contributor.objects.get(slug="fernanda-soto")
    fernanda.photo = real
    fernanda.save(update_fields=["photo"])
    libro = Publication.objects.get(slug="plaquette")
    libro.cover = real
    libro.save(update_fields=["cover"])

    call_command("seed_material_generico", "--fotos-por-evento", "1", verbosity=0)

    fernanda.refresh_from_db()
    assert fernanda.photo_id == real.pk, "pisó material real"
    assert not MediaAsset.objects.filter(
        alt_text=f"Retrato provisional de {fernanda.display_name}"
    ).exists(), "creó un marcador que no iba a asignar"
    libro.refresh_from_db()
    assert libro.cover_id == real.pk, "pisó una cubierta real"
    assert not MediaAsset.objects.filter(alt_text=f"Cubierta provisional · {libro.title}").exists()
    assert not Contributor.objects.members().filter(photo=None).exists()
    assert not Event.objects.filter(poster=None).exists()
    assert all(e.photos.count() >= 1 for e in Event.objects.all())
    # El cupo se completa, no se excede: la actividad que ya trae fotos (tres del colectivo
    # frente a un cupo de una) no recibe marcadores mezclados con ellas.
    con_fotos = Event.objects.get(slug="recital-con-fotos")
    assert [is_placeholder(f.asset) for f in con_fotos.photos.all()] == [False] * 3
    assert all(p.cover_id for p in Publication.objects.all())
    assert not Recording.objects.filter(poster=None).exists()
    assert not Partner.objects.filter(logo=None).exists()
    assert SiteProfile.load().og_image.alt_text == (
        f"Foto de grupo provisional · {identity.PROFILE['name']}"
    )

    cuantos = MediaAsset.objects.count()
    call_command("seed_material_generico", "--fotos-por-evento", "1", verbosity=0)
    assert MediaAsset.objects.count() == cuantos, "la segunda corrida duplicó recursos"


def test_placeholder_photos_do_not_count_towards_the_gallery_quota(
    settings, tmp_path, dibujantes_diminutos
):
    """Una actividad cuyas fotos son marcadores recibe el cupo entero, como si no tuviera
    ninguna; una con fotos reales, solo lo que falta."""
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path
    demo = make_event(slug="con-fotos-de-demostracion", title="Con fotos de demostración")
    for position in range(2):
        _credited(make_photo(demo, position), "Placeholder de demo (reemplazable)")
    real = make_event(slug="con-una-foto-real", title="Con una foto real")
    _credited(make_photo(real, 0), "Archivo del colectivo")

    call_command("seed_material_generico", "--fotos-por-evento", "2", verbosity=0)

    drawn = demo.photos.filter(asset__credit=PLACEHOLDER_CREDIT)
    assert drawn.count() == 2, "las fotos de demostración contaron como reales"
    assert real.photos.filter(asset__credit=PLACEHOLDER_CREDIT).count() == 1


@pytest.mark.parametrize(
    "credit,placeholder",
    [
        (PLACEHOLDER_CREDIT, True),
        ("Placeholder de demo (reemplazable)", True),
        ("Foto PROVISIONAL", True),
        ("Archivo del colectivo", False),
        ("Foto: Alguien Real", False),
        ("", False),
        (None, False),
    ],
)
def test_a_placeholder_is_recognised_by_its_credit(credit, placeholder):
    assert is_placeholder(SimpleNamespace(credit=credit)) is placeholder


@pytest.mark.parametrize(
    "generar,tamano",
    [
        (lambda: cmd._retrato("Nombre Apellido", "nombre"), (1200, 1500)),
        (lambda: cmd._foto_lectura("Recital", 1, "recital"), (2400, 1600)),
        (lambda: cmd._cubierta("Título", "Autoría", "Libro · 2024", "titulo"), (1000, 1400)),
        (lambda: cmd._logo("Fondo del Libro", "aliado:1"), (600, 300)),
        (lambda: cmd._imagen_texto("Un título largo de reseña", "Reseña", "t"), (1800, 1200)),
        (lambda: cmd._foto_grupo(["A", "B", "C"]), (2400, 1260)),
    ],
)
def test_cada_dibujante_respeta_su_proporcion(generar, tamano):
    img, formato = generar()
    assert img.size == tamano
    assert formato in ("JPEG", "PNG")


def test_afiche_y_caratula_respetan_su_proporcion():
    evento = SimpleNamespace(
        title="Recital de prueba",
        starts_at=None,
        venue_name="Sala",
        city="Santiago",
        get_type_display=lambda: "Recital",
    )
    registro = SimpleNamespace(title="Lectura", get_kind_display=lambda: "Video")
    assert cmd._afiche(evento, "recital")[0].size == (1200, 1600)
    assert cmd._caratula_registro(registro, "lectura")[0].size == (1920, 1080)
