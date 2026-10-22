"""Los datos de desarrollo, para ver en otro equipo lo mismo que en este.

    python manage.py datos_de_desarrollo exportar   # escribe backend/datos_de_desarrollo/
    python manage.py datos_de_desarrollo cargar     # en una base recién migrada y sin contenido

Viaja solo el contenido público: lo que se ve en el sitio y en la biblioteca de medios, con los
originales de sus archivos. El repositorio es público, así que NO viajan las cuentas de usuario,
las sesiones, los registros de acceso y del panel, los suscriptores del boletín, los envíos a las
convocatorias ni el historial editorial; las referencias a cuentas (`owner`, `uploaded_by`,
`user`…) quedan vacías. Tampoco los registros de prueba de subida (`test-…`, sin publicar). Las
copias de las imágenes a otros tamaños no viajan: `cargar` las rehace.
"""

import json
import shutil
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import models

CARPETA = Path(settings.BASE_DIR) / "datos_de_desarrollo"

# Lo que viaja, por nombre: un modelo nuevo no entra solo, porque podría guardar datos privados.
MODELOS = [
    "people.Contributor",
    "people.SocialLink",
    "reviews.Publisher",
    "reviews.BookAuthor",
    "reviews.Work",
    "media.MediaAsset",
    "media.Recording",
    "content.Section",
    "content.Tag",
    "content.Article",
    "content.ArticleContributor",
    "content.ReviewedWork",
    "content.Poem",
    "content.PoemContributor",
    "content.Collection",
    "content.CollectionArticle",
    "content.CollectionPoem",
    "content.Page",
    "agenda.Event",
    "agenda.EventPhoto",
    "agenda.Milestone",
    "showcase.SiteProfile",
    "showcase.SiteSocialLink",
    "showcase.Publication",
    "showcase.WhereToBuy",
    "showcase.PressMention",
    "showcase.Partner",
    "submissions.Call",
]

# Si alguno tiene filas, la base ya tiene contenido y `cargar` no la toca.
CON_CONTENIDO = ["content.Poem", "content.Article", "media.MediaAsset", "showcase.Publication"]


class Command(BaseCommand):
    help = "Exporta o carga los datos de desarrollo (solo el contenido público)."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["exportar", "cargar"])

    def handle(self, *args, accion, **options):
        if accion == "exportar":
            self.exportar()
        else:
            self.cargar()

    def exportar(self):
        objetos = []
        for etiqueta in MODELOS:
            filas = apps.get_model(etiqueta).objects.order_by("pk")
            if etiqueta == "media.Recording":
                filas = filas.exclude(slug__startswith="test-")
            objetos.extend(filas)
        datos = json.loads(serializers.serialize("json", objetos))
        # Lo que apunta a algo que no viaja (una cuenta, un registro de prueba) queda vacío: si
        # no, la carga falla por una referencia rota.
        incluidos = {(obj._meta.label, obj.pk) for obj in objetos}
        for fila in datos:
            for campo in apps.get_model(fila["model"])._meta.get_fields():
                destino = getattr(campo, "related_model", None)
                if isinstance(campo, models.ForeignKey):
                    valor = fila["fields"].get(campo.name)
                    if valor is not None and (destino._meta.label, valor) not in incluidos:
                        if not campo.null:
                            raise CommandError(
                                f"{fila['model']}.{campo.name} apunta a algo que no viaja."
                            )
                        fila["fields"][campo.name] = None
                elif isinstance(campo, models.ManyToManyField) and campo.name in fila["fields"]:
                    fila["fields"][campo.name] = [
                        v
                        for v in fila["fields"][campo.name]
                        if (destino._meta.label, v) in incluidos
                    ]
        archivos = sorted(
            {
                getattr(obj, campo.name).name
                for obj in objetos
                for campo in obj._meta.get_fields()
                if isinstance(campo, models.FileField) and getattr(obj, campo.name)
            }
        )
        if CARPETA.exists():
            shutil.rmtree(CARPETA)
        (CARPETA / "media").mkdir(parents=True)
        texto = json.dumps(datos, ensure_ascii=False, indent=1)
        (CARPETA / "datos.json").write_text(f"{texto}\n", encoding="utf-8")
        for nombre in archivos:
            destino = CARPETA / "media" / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            with default_storage.open(nombre, "rb") as origen:
                destino.write_bytes(origen.read())
        self.stdout.write(f"{len(datos)} filas y {len(archivos)} archivos en {CARPETA}")

    def cargar(self):
        if not settings.DEBUG:
            raise CommandError("Solo en desarrollo (DEBUG): son datos de prueba.")
        if not (CARPETA / "datos.json").exists():
            raise CommandError(f"No está {CARPETA / 'datos.json'}.")
        llenos = [e for e in CON_CONTENIDO if apps.get_model(e).objects.exists()]
        if llenos:
            raise CommandError(
                f"La base ya tiene contenido ({', '.join(llenos)}): no se pisa. "
                "Para empezar de cero: docker compose down -v y vuelve a levantar."
            )
        copiados = 0
        for archivo in sorted((CARPETA / "media").rglob("*")):
            nombre = archivo.relative_to(CARPETA / "media").as_posix()
            if archivo.is_file() and not default_storage.exists(nombre):
                with archivo.open("rb") as origen:
                    default_storage.save(nombre, File(origen))
                copiados += 1
        call_command("loaddata", str(CARPETA / "datos.json"), verbosity=0)
        call_command("generate_image_derivatives", verbosity=0)
        # La obra de la portada pide sus propias copias (AVIF y WebP), que hace SiteProfile al guardarse.
        apps.get_model("showcase.SiteProfile").load().save()
        self.stdout.write(
            f"Cargado: {copiados} archivos y los datos de desarrollo. Crea tu cuenta para el panel "
            "con: python manage.py createsuperuser"
        )
