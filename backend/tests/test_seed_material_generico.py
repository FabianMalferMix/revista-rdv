"""`seed_material_generico` dibuja marcadores con proporciones reales y los asigna sin
pisar material real. Como `seed_demo`, se niega a correr en producción.

Las pruebas de asignación sustituyen los dibujantes por imágenes diminutas: lo que se
verifica es la lógica (guardia, asignación, idempotencia), no el dibujo. El dibujo se
prueba aparte, una vez por tipo, comprobando solo el tamaño del lienzo.
"""

from io import BytesIO
from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from PIL import Image

from apps.agenda.models import Event
from apps.media.management.commands import seed_material_generico as cmd
from apps.media.models import MediaAsset, Recording
from apps.people.models import Contributor
from apps.showcase.models import Partner, Publication, SiteProfile

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


@override_settings(DEBUG=False)
def test_se_niega_a_correr_con_debug_apagado():
    with pytest.raises(CommandError, match="producción"):
        call_command("seed_material_generico")
    assert not MediaAsset.objects.filter(alt_text__icontains="provisional").exists()


@override_settings(DEBUG=False)
def test_asigna_marcadores_sin_pisar_material_real_y_es_idempotente(
    settings, tmp_path, dibujantes_diminutos
):
    settings.MEDIA_ROOT = tmp_path
    call_command("seed_demo", "--force", verbosity=0)

    # Material REAL simulado: una integrante con retrato cuyo crédito no es de marcador.
    real = MediaAsset(alt_text="Retrato de Fernanda Soto", credit="Foto: Alguien Real")
    real.file.save("real.png", ContentFile(_png_diminuto()), save=True)
    fernanda = Contributor.members().first()
    fernanda.photo = real
    fernanda.save(update_fields=["photo"])
    libro = Publication.objects.first()
    libro.cover = real
    libro.save(update_fields=["cover"])

    call_command("seed_material_generico", "--force", "--fotos-por-evento", "1", verbosity=0)

    fernanda.refresh_from_db()
    assert fernanda.photo_id == real.pk, "pisó material real"
    assert not MediaAsset.objects.filter(
        alt_text=f"Retrato provisional de {fernanda.display_name}"
    ).exists(), "creó un marcador que no iba a asignar"
    libro.refresh_from_db()
    assert libro.cover_id == real.pk, "pisó una cubierta real"
    assert not MediaAsset.objects.filter(alt_text=f"Cubierta provisional · {libro.title}").exists()
    assert not Contributor.members().filter(photo=None).exists()
    assert not Event.objects.filter(poster=None).exists()
    assert all(e.photos.count() >= 1 for e in Event.objects.all())
    # El cupo se completa, no se excede: un evento que ya trae fotos (aquí, las tres de la
    # siembra frente a un cupo de una) no recibe marcadores mezclados con ellas.
    con_fotos = [e for e in Event.objects.all() if e.photos.exclude(asset__credit=cmd.CREDITO)]
    assert con_fotos, "la siembra ya no trae un evento con fotos: revisar esta prueba"
    assert all(not e.photos.filter(asset__credit=cmd.CREDITO).exists() for e in con_fotos)
    assert all(p.cover_id for p in Publication.objects.all())
    assert not Recording.objects.filter(poster=None).exists()
    assert not Partner.objects.filter(logo=None).exists()
    perfil = SiteProfile.load()
    assert perfil.og_image_id is not None
    assert len(perfil.manifesto.split()) >= 40

    cuantos = MediaAsset.objects.count()
    call_command("seed_material_generico", "--force", "--fotos-por-evento", "1", verbosity=0)
    assert MediaAsset.objects.count() == cuantos, "la segunda corrida duplicó recursos"


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
