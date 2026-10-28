"""Los datos de desarrollo (`datos_de_desarrollo exportar|cargar|marcar`): la copia que viaja en
el repositorio para ver en otro equipo lo mismo que en el de desarrollo.

El repositorio es público: solo puede viajar lo que el sitio ya muestra. Ni cuentas, ni
sesiones, ni registros de acceso, ni suscriptores, ni envíos a convocatorias, ni el historial
editorial, ni lo no publicado, salvo las piezas de demostración del flujo editorial.
"""

import json
import re

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models

from apps.content.management.commands import datos_de_desarrollo as comando
from apps.content.models import Article, EditorialStatus
from apps.devtools.models import DevelopmentMarker
from apps.media.models import MediaAsset
from apps.showcase.models import Publication
from tests.factories import make_image, make_publication

TEXTO = (comando.CARPETA / "datos.json").read_text("utf-8")
DATOS = json.loads(TEXTO)
# El correo del colectivo, que el dueño aprobó publicar, y uno inventado de los textos largos.
CORREOS_PUBLICOS = {
    "repitentesdelverso@gmail.com",
    "lecturas.y.relecturas.obstinadas.del.taller.de.los.jueves@correo-electronico-del-colectivo.cl",
}
ARCHIVOS = {
    "media.mediaasset": "file",
    "media.recording": "file",
    "showcase.siteprofile": "dossier_pdf",
    "showcase.publication": "pdf",
}


def etiqueta(fila):
    return apps.get_model(fila["model"])._meta.label


def test_en_el_repositorio_solo_viaja_el_contenido_publico():
    modelos = {fila["model"] for fila in DATOS}
    assert modelos <= {m.lower() for m in comando.MODELOS}
    privadas = {"auth", "sessions", "admin", "axes", "community", "devtools"}
    assert not [m for m in modelos if m.split(".")[0] in privadas]
    assert "submissions.submission" not in modelos
    assert "content.editorialtransition" not in modelos


def test_cada_modelo_y_cada_campo_tienen_su_regla():
    """Un modelo o un campo nuevo no viaja hasta que alguien decide si es público."""
    assert comando.unclassified() == []


def test_solo_viaja_lo_publicado_y_las_piezas_de_demostracion():
    for fila in DATOS:
        campos = fila["fields"]
        if "status" in campos:
            demo = comando.DEMO_UNPUBLISHED.get(etiqueta(fila), set())
            assert campos["status"] == "published" or campos["slug"] in demo, fila
        if "published" in campos:
            assert campos["published"], fila
        if fila["model"] == "showcase.partner":
            assert campos["active"], fila


def test_sin_campos_privados():
    for fila in DATOS:
        privados = comando.PRIVATE_FIELDS.get(etiqueta(fila), set())
        assert not privados & set(fila["fields"]), fila["model"]


def test_cada_imagen_que_viaja_la_usa_algo_que_viaja():
    usadas = {
        fila["fields"][campo.name]
        for fila in DATOS
        for campo in apps.get_model(fila["model"])._meta.get_fields()
        if getattr(campo, "related_model", None) is MediaAsset and campo.name in fila["fields"]
    }
    imagenes = {fila["pk"] for fila in DATOS if fila["model"] == "media.mediaasset"}
    assert imagenes and imagenes <= usadas


def test_sin_contrasenas_ni_cuentas_ni_correos_privados():
    assert "pbkdf2" not in TEXTO and '"password"' not in TEXTO
    assert set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", TEXTO)) <= CORREOS_PUBLICOS
    # Las referencias a cuentas, leídas de los modelos: `author` de una mención en prensa es el
    # nombre del periodista, no una cuenta.
    usuario = apps.get_model(settings.AUTH_USER_MODEL)
    for fila in DATOS:
        for campo in apps.get_model(fila["model"])._meta.get_fields():
            if isinstance(campo, models.ForeignKey) and campo.related_model is usuario:
                assert fila["fields"].get(campo.name) is None, (fila["model"], campo.name)


def test_cada_archivo_que_nombra_viaja_con_el():
    for fila in DATOS:
        campo = ARCHIVOS.get(fila["model"])
        if campo and fila["fields"][campo]:
            assert (comando.CARPETA / "media" / fila["fields"][campo]).is_file()


@pytest.mark.django_db
def test_la_copia_entra_en_una_base_recien_migrada():
    """Si un cambio de modelo la rompe (un campo nuevo obligatorio, uno que se va), esto falla
    y hay que volver a exportarla."""
    call_command("loaddata", str(comando.CARPETA / "datos.json"), verbosity=0)
    assert Publication.objects.count() == sum(f["model"] == "showcase.publication" for f in DATOS)


@pytest.fixture
def carpeta(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setattr(comando, "CARPETA", tmp_path / "datos")
    return tmp_path / "datos"


@pytest.mark.django_db
def test_de_ida_y_vuelta_sin_la_cuenta(settings, carpeta, django_user_model):
    settings.DEBUG = True
    DevelopmentMarker.mark()
    tapa = make_image("tapa-ida-y-vuelta")
    tapa.uploaded_by = django_user_model.objects.create_user("alguien", "alguien@ejemplo.cl")
    tapa.save()
    make_publication(slug="ida-y-vuelta", title="Ida y vuelta", cover=tapa)
    call_command("datos_de_desarrollo", "exportar", verbosity=0)
    exportado = (carpeta / "datos.json").read_text("utf-8")
    assert "alguien" not in exportado
    assert (carpeta / "media" / tapa.file.name).is_file()
    nombre = tapa.file.name
    Publication.objects.all().delete()
    MediaAsset.objects.all().delete()
    call_command("datos_de_desarrollo", "cargar", verbosity=0)
    cargada = Publication.objects.get(slug="ida-y-vuelta")
    assert cargada.cover.file.name == nombre and cargada.cover.uploaded_by is None
    assert cargada.cover.file.storage.exists(nombre)


@pytest.mark.django_db
def test_lo_no_publicado_y_lo_que_nadie_usa_no_viajan(carpeta):
    DevelopmentMarker.mark()
    Article.objects.create(slug="a-la-vista", title="Publicado", status=EditorialStatus.PUBLISHED)
    Article.objects.create(slug="borrador-secreto", title="Borrador", status=EditorialStatus.DRAFT)
    make_publication(slug="sin-publicar", published=False)
    make_image("suelta", alt="Imagen que nada usa")
    call_command("datos_de_desarrollo", "exportar", verbosity=0)
    exportado = (carpeta / "datos.json").read_text("utf-8")
    assert '"a-la-vista"' in exportado
    assert "borrador-secreto" not in exportado and "sin-publicar" not in exportado
    assert "Imagen que nada usa" not in exportado
    assert not list((carpeta / "media").rglob("suelta*"))


@pytest.mark.django_db
def test_exportar_exige_una_base_marcada_como_de_desarrollo(carpeta):
    with pytest.raises(CommandError, match="no está marcada como de desarrollo"):
        call_command("datos_de_desarrollo", "exportar", verbosity=0)
    assert not carpeta.exists()


@pytest.mark.django_db
def test_un_fallo_a_mitad_deja_la_copia_anterior(carpeta):
    DevelopmentMarker.mark()
    carpeta.mkdir()
    (carpeta / "datos.json").write_text("la copia anterior", encoding="utf-8")
    tapa = make_image("tapa-perdida")
    make_publication(slug="con-tapa-perdida", cover=tapa)
    tapa.file.storage.delete(tapa.file.name)
    with pytest.raises(FileNotFoundError):
        call_command("datos_de_desarrollo", "exportar", verbosity=0)
    assert (carpeta / "datos.json").read_text("utf-8") == "la copia anterior"


@pytest.mark.django_db
def test_marcar_deja_la_base_lista_para_exportar(settings):
    settings.DEBUG = True
    assert not DevelopmentMarker.is_marked()
    call_command("datos_de_desarrollo", "marcar", verbosity=0)
    assert DevelopmentMarker.is_marked()


@pytest.mark.django_db
def test_cargar_no_pisa_una_base_con_contenido(settings):
    settings.DEBUG = True
    make_publication(slug="ya-estaba")
    with pytest.raises(CommandError, match="ya tiene contenido"):
        call_command("datos_de_desarrollo", "cargar")


@pytest.mark.parametrize("accion", ["cargar", "marcar"])
def test_cargar_y_marcar_solo_en_desarrollo(settings, accion):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="Solo en desarrollo"):
        call_command("datos_de_desarrollo", accion)
