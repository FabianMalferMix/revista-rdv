"""Los datos de desarrollo (`datos_de_desarrollo exportar|cargar`): la copia que viaja en el
repositorio para ver en otro equipo lo mismo que en el de desarrollo.

El repositorio es público: solo puede viajar contenido público. Ni cuentas, ni sesiones, ni
registros de acceso, ni suscriptores, ni envíos a convocatorias, ni el historial editorial.
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


def test_en_el_repositorio_solo_viaja_el_contenido_publico():
    modelos = {fila["model"] for fila in DATOS}
    assert modelos <= {m.lower() for m in comando.MODELOS}
    privadas = {"auth", "sessions", "admin", "axes", "community"}
    assert not [m for m in modelos if m.split(".")[0] in privadas]
    assert "submissions.submission" not in modelos
    assert "content.editorialtransition" not in modelos


def test_sin_contrasenas_ni_cuentas_ni_correos_privados():
    assert "pbkdf2" not in TEXTO and '"password"' not in TEXTO
    assert set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", TEXTO)) <= CORREOS_PUBLICOS
    # Las referencias a cuentas, leídas de los modelos: `author` de una mención en prensa es el
    # nombre del periodista, no una cuenta.
    usuario = apps.get_model(settings.AUTH_USER_MODEL)
    for fila in DATOS:
        for campo in apps.get_model(fila["model"])._meta.get_fields():
            if isinstance(campo, models.ForeignKey) and campo.related_model is usuario:
                assert fila["fields"][campo.name] is None, (fila["model"], campo.name)


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


@pytest.mark.django_db
def test_de_ida_y_vuelta_sin_la_cuenta(settings, tmp_path, monkeypatch, django_user_model):
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setattr(comando, "CARPETA", tmp_path / "datos")
    tapa = make_image("tapa-ida-y-vuelta")
    tapa.uploaded_by = django_user_model.objects.create_user("alguien", "alguien@ejemplo.cl")
    tapa.save()
    make_publication(slug="ida-y-vuelta", title="Ida y vuelta", cover=tapa)
    call_command("datos_de_desarrollo", "exportar", verbosity=0)
    exportado = (tmp_path / "datos" / "datos.json").read_text("utf-8")
    assert "alguien" not in exportado
    assert (tmp_path / "datos" / "media" / tapa.file.name).is_file()
    nombre = tapa.file.name
    Publication.objects.all().delete()
    MediaAsset.objects.all().delete()
    call_command("datos_de_desarrollo", "cargar", verbosity=0)
    cargada = Publication.objects.get(slug="ida-y-vuelta")
    assert cargada.cover.file.name == nombre and cargada.cover.uploaded_by is None
    assert cargada.cover.file.storage.exists(nombre)


@pytest.mark.django_db
def test_cargar_no_pisa_una_base_con_contenido(settings):
    settings.DEBUG = True
    make_publication(slug="ya-estaba")
    with pytest.raises(CommandError, match="ya tiene contenido"):
        call_command("datos_de_desarrollo", "cargar")


def test_cargar_solo_en_desarrollo(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="Solo en desarrollo"):
        call_command("datos_de_desarrollo", "cargar")
