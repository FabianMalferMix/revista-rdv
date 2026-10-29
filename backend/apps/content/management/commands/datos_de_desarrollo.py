"""Los datos de desarrollo, para ver en otro equipo lo mismo que en este.

    python manage.py datos_de_desarrollo exportar   # escribe backend/datos_de_desarrollo/
    python manage.py datos_de_desarrollo cargar     # en una base recién migrada y sin contenido
    python manage.py datos_de_desarrollo marcar     # declara de desarrollo la base actual

El repositorio es público, así que viaja solo lo que el sitio ya muestra:

- lo publicado (`PUBLIC_ROWS`), más las piezas de `DEMO_UNPUBLISHED`, que enseñan el flujo
  editorial en el panel;
- lo que depende de ello (`OWNED_ROWS`: autorías, fotos, enlaces);
- y lo que eso nombra (`REFERENCED_ROWS`: sus imágenes, sus autoras, su catálogo), con los
  originales de sus archivos.

Cada campo de cada modelo está en `PUBLIC_FIELDS` o en `PRIVATE_FIELDS`, y un campo nuevo hace
fallar la exportación hasta que alguien decida. No viajan las cuentas, las sesiones, los
registros de acceso y del panel, los suscriptores, los envíos ni el historial editorial; las
referencias a algo que no viaja quedan vacías. Las copias de las imágenes a otros tamaños
tampoco: `cargar` las rehace.

`exportar` solo corre en una base marcada como de desarrollo (con `cargar`, `marcar` o
`seed_demo`): una copia de producción restaurada en local no lo está.
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
from django.db.models.functions import Now

from apps.devtools.models import DevelopmentMarker

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

# Las filas que el sitio muestra por sí mismas, a partir del manager de cada modelo. Qué está
# publicado lo decide su QuerySet (config/publishing.py), el mismo que usan las vistas.
PUBLIC_ROWS = {
    "content.Article": lambda rows: rows.published(),
    "content.Poem": lambda rows: rows.published(),
    "content.Collection": lambda rows: rows.published(),
    "content.Page": lambda rows: rows.published(),
    "media.Recording": lambda rows: rows.published().exclude(slug__startswith="test-"),
    "agenda.Event": lambda rows: rows.published(),
    "agenda.Milestone": lambda rows: rows.all(),
    "showcase.SiteProfile": lambda rows: rows.all(),
    "showcase.Publication": lambda rows: rows.published(),
    "showcase.PressMention": lambda rows: rows.published(),
    "showcase.Partner": lambda rows: rows.published(),
    "submissions.Call": lambda rows: rows.filter(opens_at__lte=Now()),
    "people.Contributor": lambda rows: rows.filter(is_member=True),
    "reviews.Work": lambda rows: rows.filter(
        publicacion__in=apps.get_model("showcase.Publication").objects.published()
    ),
}

# Las piezas sin publicar que viajan igual, para enseñar el flujo editorial en el panel.
DEMO_UNPUBLISHED = {
    "content.Article": {"resena-en-revision", "resena-antologia-del-margen"},
    "content.Poem": {"borrador-de-invierno"},
}

# Las filas que dependen de otras: viajan si viajan las filas a las que apuntan estos campos.
OWNED_ROWS = {
    "people.SocialLink": ("contributor",),
    "content.ArticleContributor": ("article",),
    "content.ReviewedWork": ("article",),
    "content.PoemContributor": ("poem",),
    "content.CollectionArticle": ("collection", "article"),
    "content.CollectionPoem": ("collection", "poem"),
    "agenda.EventPhoto": ("event",),
    "showcase.SiteSocialLink": ("profile",),
    "showcase.WhereToBuy": ("publication",),
}

# Lo que solo existe porque algo que viaja lo nombra: viaja si una fila que viaja lo referencia.
REFERENCED_ROWS = {
    "media.MediaAsset",
    "content.Section",
    "content.Tag",
    "reviews.Work",
    "reviews.Publisher",
    "reviews.BookAuthor",
    "people.Contributor",
}

# Los campos que no viajan: las cuentas del panel y el vector de búsqueda, que el trigger de la
# base rehace al cargar.
PRIVATE_FIELDS = {
    "people.Contributor": {"user"},
    "media.MediaAsset": {"uploaded_by"},
    "content.Article": {"owner", "search_vector"},
    "content.Poem": {"owner", "search_vector"},
}

# Los campos que viajan, todos visibles en el sitio o necesarios para cargarlo.
PUBLIC_FIELDS = {
    "people.Contributor": {
        "slug", "display_name", "bio", "photo", "website", "is_member", "active", "role",
        "member_since", "short_bio", "poetics", "position",
    },
    "people.SocialLink": {"contributor", "platform", "url", "position"},
    "reviews.Publisher": {"slug", "name", "country", "website"},
    "reviews.BookAuthor": {"slug", "name", "bio"},
    "reviews.Work": {
        "slug", "title", "kind", "publisher", "publication_year", "isbn",
        "cover_image", "description", "publicacion", "authors",
    },
    "media.MediaAsset": {"file", "alt_text", "caption", "credit", "width", "height", "created_at"},
    "media.Recording": {
        "slug", "title", "kind", "file", "embed_url", "poster", "description", "recorded_on",
        "duration_minutes", "event", "featured", "published", "published_at", "position",
        "created_at", "participants",
    },
    "content.Section": {"slug", "name", "description", "position"},
    "content.Tag": {"slug", "name"},
    "content.Article": {
        "status", "published_at", "created_at", "updated_at", "slug", "title", "subtitle", "body",
        "excerpt", "type", "section", "cover_image", "og_image", "reading_time",
        "seo_title", "seo_description", "tags",
    },
    "content.ArticleContributor": {"article", "contributor", "position"},
    "content.ReviewedWork": {"article", "work"},
    "content.Poem": {
        "status", "published_at", "created_at", "updated_at", "slug", "title", "epigraph", "body",
        "recording", "og_image", "seo_title", "seo_description",
    },
    "content.PoemContributor": {"poem", "contributor", "position"},
    "content.Collection": {
        "slug", "title", "description", "intro", "cover_image", "status", "published_at",
    },
    "content.CollectionArticle": {"collection", "article", "position"},
    "content.CollectionPoem": {"collection", "poem", "position"},
    "content.Page": {"slug", "title", "body", "status", "seo_title", "seo_description"},
    "agenda.Event": {
        "slug", "title", "type", "starts_at", "ends_at", "venue_name", "address", "city",
        "description", "poster", "is_external", "host", "registration_url", "published",
        "participants",
    },
    "agenda.EventPhoto": {"event", "asset", "caption", "position"},
    "agenda.Milestone": {"year", "title", "description"},
    "showcase.SiteProfile": {
        "name", "tagline", "manifesto", "founded_year", "location", "general_email",
        "booking_email", "phone", "featured_recording", "featured_poem", "dossier_pdf",
        "og_image", "hero_image", "hero_image_phone", "updated_at",
    },
    "showcase.SiteSocialLink": {"profile", "platform", "url", "position"},
    "showcase.Publication": {
        "slug", "title", "kind", "publisher", "year", "isbn", "cover", "synopsis", "is_own",
        "pdf", "featured", "published", "position", "participants",
    },
    "showcase.WhereToBuy": {"publication", "label", "url", "position"},
    "showcase.PressMention": {
        "title", "outlet", "author", "kind", "published_on", "url", "quote", "logo",
        "published", "position",
    },
    "showcase.Partner": {"name", "kind", "logo", "url", "description", "active", "position"},
    "submissions.Call": {"slug", "title", "description", "opens_at", "closes_at"},
}  # fmt: skip


def serialized_fields(model):
    """Los campos que el serializador escribe: los propios y los M2M sin modelo intermedio."""
    own = {f.name for f in model._meta.local_fields if not f.primary_key}
    many = {
        f.name for f in model._meta.local_many_to_many if f.remote_field.through._meta.auto_created
    }
    return own | many


def unclassified():
    """Lo que falta decidir: modelos sin regla de filas y campos sin clasificar."""
    problems = []
    for label in MODELOS:
        if label not in PUBLIC_ROWS and label not in OWNED_ROWS and label not in REFERENCED_ROWS:
            problems.append(f"{label}: sin regla de filas")
        fields = serialized_fields(apps.get_model(label))
        public, private = PUBLIC_FIELDS.get(label, set()), PRIVATE_FIELDS.get(label, set())
        problems += [
            f"{label}.{name}: sin clasificar" for name in sorted(fields - public - private)
        ]
        problems += [f"{label}.{name}: en las dos listas" for name in sorted(public & private)]
        problems += [f"{label}.{name}: no existe" for name in sorted((public | private) - fields)]
    return problems


def exported_pks():
    """Las claves de las filas que viajan, por modelo."""
    included = {label: set() for label in MODELOS}
    for label, public in PUBLIC_ROWS.items():
        objects = apps.get_model(label).objects
        rows = public(objects)
        demo = DEMO_UNPUBLISHED.get(label)
        if demo:
            rows = rows | objects.filter(slug__in=demo)
        included[label] |= set(rows.values_list("pk", flat=True))
    changed = True
    while changed:
        changed = False
        for label, owners in OWNED_ROWS.items():
            model = apps.get_model(label)
            filters = {
                f"{name}__in": included[model._meta.get_field(name).related_model._meta.label]
                for name in owners
            }
            found = set(model.objects.filter(**filters).values_list("pk", flat=True))
            changed |= not found <= included[label]
            included[label] |= found
        for label in MODELOS:
            model = apps.get_model(label)
            for name in PUBLIC_FIELDS[label]:
                field = model._meta.get_field(name)
                target = field.related_model._meta.label if field.is_relation else None
                if target not in REFERENCED_ROWS or not included[label]:
                    continue
                rows = model.objects.filter(pk__in=included[label], **{f"{name}__isnull": False})
                found = set(rows.values_list(name, flat=True))
                changed |= not found <= included[target]
                included[target] |= found
    return included


class Command(BaseCommand):
    help = "Exporta, carga o marca los datos de desarrollo (solo el contenido público)."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["exportar", "cargar", "marcar"])

    def handle(self, *args, accion, **options):
        getattr(self, accion)()

    def exportar(self):
        if not DevelopmentMarker.is_marked():
            raise CommandError(
                "Esta base no está marcada como de desarrollo, y su contenido iría al repositorio "
                "público. Si lo es, márcala con: python manage.py datos_de_desarrollo marcar"
            )
        if problems := unclassified():
            raise CommandError(
                "Falta decidir qué viaja (PUBLIC_ROWS, OWNED_ROWS, REFERENCED_ROWS, "
                f"PUBLIC_FIELDS o PRIVATE_FIELDS): {'; '.join(problems)}"
            )
        included = exported_pks()
        objetos = []
        for etiqueta in MODELOS:
            modelo = apps.get_model(etiqueta)
            objetos.extend(modelo.objects.filter(pk__in=included[etiqueta]).order_by("pk"))
        datos = json.loads(serializers.serialize("json", objetos))
        claves = {(obj._meta.label, obj.pk) for obj in objetos}
        for fila in datos:
            modelo = apps.get_model(fila["model"])
            for nombre in PRIVATE_FIELDS.get(modelo._meta.label, ()):
                fila["fields"].pop(nombre, None)
            # Lo que apunta a algo que no viaja queda vacío: si no, la carga falla por una
            # referencia rota.
            for campo in modelo._meta.get_fields():
                if campo.name not in fila["fields"]:
                    continue
                destino = getattr(campo, "related_model", None)
                if isinstance(campo, models.ForeignKey):
                    valor = fila["fields"][campo.name]
                    if valor is not None and (destino._meta.label, valor) not in claves:
                        if not campo.null:
                            raise CommandError(
                                f"{fila['model']}.{campo.name} apunta a algo que no viaja."
                            )
                        fila["fields"][campo.name] = None
                elif isinstance(campo, models.ManyToManyField):
                    fila["fields"][campo.name] = [
                        v for v in fila["fields"][campo.name] if (destino._meta.label, v) in claves
                    ]
        archivos = {}
        for obj in objetos:
            for campo in obj._meta.get_fields():
                if isinstance(campo, models.FileField) and getattr(obj, campo.name):
                    archivo = getattr(obj, campo.name)
                    if archivo.storage is not default_storage:
                        raise CommandError(
                            f"{obj._meta.label}.{campo.name} no usa el almacén público: "
                            "sus archivos no pueden ir al repositorio."
                        )
                    archivos[archivo.name] = archivo.storage
        # Se escribe aparte y se sustituye al final: un fallo a mitad deja la copia anterior.
        nueva = CARPETA.with_name(f"{CARPETA.name}.tmp")
        if nueva.exists():
            shutil.rmtree(nueva)
        (nueva / "media").mkdir(parents=True)
        texto = json.dumps(datos, ensure_ascii=False, indent=1)
        (nueva / "datos.json").write_text(f"{texto}\n", encoding="utf-8")
        for nombre, almacen in sorted(archivos.items()):
            destino = nueva / "media" / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            with almacen.open(nombre, "rb") as origen:
                destino.write_bytes(origen.read())
        if CARPETA.exists():
            shutil.rmtree(CARPETA)
        nueva.rename(CARPETA)
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
        DevelopmentMarker.mark()
        self.stdout.write(
            f"Cargado: {copiados} archivos y los datos de desarrollo. Crea tu cuenta para el panel "
            "con: python manage.py createsuperuser"
        )

    def marcar(self):
        if not settings.DEBUG:
            raise CommandError("Solo en desarrollo (DEBUG): marca una base de datos de prueba.")
        DevelopmentMarker.mark()
        self.stdout.write("Base marcada como de desarrollo: ya se puede exportar desde aquí.")
