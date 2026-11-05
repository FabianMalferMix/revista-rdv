"""Los datos de desarrollo: la copia del contenido con que se puebla cualquier base de desarrollo.

    python manage.py datos_de_desarrollo cargar     # puebla una base recién migrada
    python manage.py datos_de_desarrollo exportar   # escribe backend/datos_de_desarrollo/
    python manage.py datos_de_desarrollo marcar     # declara de desarrollo la base actual

`cargar` es el único camino para poblar desarrollo; también lo usan tools/ux/preparar-entorno.sh
y el job navegador del CI. Copia los archivos, carga las filas de `datos.json` con sus fechas
corridas (lo que estaba a N días de la exportación queda a N días de hoy), pone la identidad
del colectivo (apps/devtools/identity.py) y rehace las copias de las imágenes. No toca lo que
dejan las migraciones: la copia no trae las páginas legales, que `migrate` crea con su texto
vigente, y las páginas se buscan por su slug. En una base de desarrollo que ya tiene contenido
no hace nada; en una con contenido que no se declara de desarrollo, se niega.

El repositorio es público, así que viaja solo lo que el sitio ya muestra:

- lo publicado (`PUBLIC_ROWS`), más las piezas de `DEMO_UNPUBLISHED`, que enseñan el flujo
  editorial en el panel;
- lo que depende de ello (`OWNED_ROWS`: autorías, fotos, enlaces);
- y lo que eso nombra (`REFERENCED_ROWS`: sus imágenes, sus autoras, su catálogo), con los
  originales de sus archivos.

Cada campo de cada modelo está en `PUBLIC_FIELDS`, en `PRIVATE_FIELDS` o en `IDENTITY_FIELDS`, y
un campo nuevo hace fallar la exportación hasta que alguien decida; solo se escriben los de
`PUBLIC_FIELDS`. Los que calcula la base, como el vector de búsqueda, no viajan: los vuelve a
calcular al guardar cada fila. Tampoco las cuentas, las sesiones, los registros de acceso y del
panel, los suscriptores, los envíos ni el historial editorial; las referencias a algo que no
viaja quedan vacías. Ni las copias de las imágenes a otros tamaños: `cargar` las rehace.

Como todo comando de desarrollo, las tres acciones solo corren con DEBUG y fuera de producción
(DevelopmentCommand). Y `exportar`, además, solo en una base marcada como de desarrollo (con
`cargar` o `marcar`): una copia de producción restaurada en local no lo está, aunque corra con
DEBUG.
"""

import json
import shutil
import tempfile
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models.functions import Now
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.content.models import LEGAL_PAGES
from apps.devtools import identity
from apps.devtools.management.base import DevelopmentCommand
from apps.devtools.models import DevelopmentMarker
from apps.showcase.models import SiteProfile

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
    "showcase.Publication",
    "showcase.WhereToBuy",
    "showcase.PressMention",
    "showcase.Partner",
    "submissions.Call",
]

# Lo que no viaja, con su motivo. Todo modelo de las apps está en MODELOS o aquí.
NOT_EXPORTED = {
    "community.NewsletterSubscriber": "Correos de personas reales: datos personales.",
    "submissions.Submission": "Propuestas de autores externos, con su correo y su manuscrito.",
    "content.EditorialNote": "Discusión interna del equipo sobre piezas que pueden no publicarse.",
    "content.EditorialTransition": "Bitácora interna, con las cuentas del panel.",
    "people.RoleGrant": "Lo que setup_groups repartió en esta base; lo rehace en cada una.",
    "devtools.DevelopmentMarker": "La marca de esta base, no su contenido: la pone `cargar`.",
    "showcase.SiteSocialLink": "Las redes del colectivo son de su identidad, que pone `cargar`.",
}

# Si alguno tiene filas, la base ya tiene contenido y `cargar` no la toca.
CON_CONTENIDO = ["content.Poem", "content.Article", "media.MediaAsset", "showcase.Publication"]

# Las filas que el sitio muestra por sí mismas, a partir del manager de cada modelo. Qué está
# publicado lo decide su QuerySet (config/publishing.py), el mismo que usan las vistas. Las
# páginas legales no viajan: `migrate` las crea con su texto vigente (apps/content/legal.py). Las
# secciones salen todas en el sitemap, también las que aún no tienen textos.
PUBLIC_ROWS = {
    "content.Article": lambda rows: rows.published(),
    "content.Poem": lambda rows: rows.published(),
    "content.Collection": lambda rows: rows.published(),
    "content.Page": lambda rows: rows.published().exclude(slug__in=LEGAL_PAGES),
    "content.Section": lambda rows: rows.all(),
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
    "showcase.WhereToBuy": ("publication",),
}

# Lo que solo existe porque algo que viaja lo nombra: viaja si una fila que viaja lo referencia.
REFERENCED_ROWS = {
    "media.MediaAsset",
    "content.Tag",
    "reviews.Work",
    "reviews.Publisher",
    "reviews.BookAuthor",
    "people.Contributor",
}

# Los modelos de los que también las migraciones crean filas (las páginas legales): sus filas
# viajan sin clave primaria y `cargar` las busca por su slug, para dejar como están las que ya
# hay y añadir las demás. Por eso nada que viaja puede apuntarles (lo comprueba `unclassified`).
BY_SLUG = {"content.Page"}

# El perfil del sitio es una fila única, la 1 (SiteProfile.load()): la migración la crea vacía y
# la copia la llena.
FILLED_IN_PLACE = {"showcase.SiteProfile"}

# Los campos que no viajan: las cuentas del panel y lo que el servicio de imágenes vuelve a medir
# al cargar.
PRIVATE_FIELDS = {
    "people.Contributor": {"user"},
    "media.MediaAsset": {"uploaded_by", "metadata_stripped_at", "border_color", "derivatives"},
    "content.Article": {"owner"},
    "content.Poem": {"owner"},
}

# Los campos que no viajan porque son la identidad del colectivo: `cargar` los pone desde
# apps/devtools/identity.py, y `exportar` exige que la base tenga esa misma.
IDENTITY_FIELDS = {"showcase.SiteProfile": set(identity.PROFILE)}

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
        "slug", "title", "kind", "file", "embed_url", "poster", "description", "transcript",
        "recorded_on",
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
        "featured_recording", "featured_poem", "dossier_pdf", "og_image", "hero_image",
        "hero_image_phone", "updated_at",
    },
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
    """Los campos que pueden viajar: los propios salvo la clave y los que calcula la base (una
    columna generada se rehace al guardar), y los M2M sin modelo intermedio."""
    own = {f.name for f in model._meta.local_fields if not f.primary_key and not f.generated}
    many = {
        f.name for f in model._meta.local_many_to_many if f.remote_field.through._meta.auto_created
    }
    return own | many


def unclassified():
    """Lo que falta decidir: modelos sin regla de filas, campos sin clasificar y referencias a lo
    que viaja sin clave."""
    problems = []
    for label in MODELOS:
        if label not in PUBLIC_ROWS and label not in OWNED_ROWS and label not in REFERENCED_ROWS:
            problems.append(f"{label}: sin regla de filas")
        model = apps.get_model(label)
        fields = serialized_fields(model)
        lists = [
            PUBLIC_FIELDS.get(label, set()),
            PRIVATE_FIELDS.get(label, set()),
            IDENTITY_FIELDS.get(label, set()),
        ]
        classified = set().union(*lists)
        problems += [f"{label}.{name}: sin clasificar" for name in sorted(fields - classified)]
        problems += [
            f"{label}.{name}: en dos listas"
            for name in sorted(classified)
            if sum(name in names for names in lists) > 1
        ]
        problems += [f"{label}.{name}: no existe" for name in sorted(classified - fields)]
        for name in sorted(PUBLIC_FIELDS.get(label, set()) & fields):
            field = model._meta.get_field(name)
            if field.is_relation and field.related_model._meta.label in BY_SLUG:
                problems.append(f"{label}.{name}: apunta a algo que viaja sin clave")
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


def read_copy(path):
    """La fecha de exportación de una copia y sus filas. Una copia sin fecha, que es una lista de
    filas, también se lee: sus fechas no se corren."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return None, data
    return parse_datetime(data["exported_at"]), data["objects"]


def days_since(exported_at):
    """Los días enteros que pasaron desde la exportación, en hora local: lo que estaba en el
    pasado al exportar sigue en el pasado. Sin fecha, ninguno."""
    if exported_at is None:
        return 0
    now = timezone.localtime().replace(tzinfo=None)
    return (now - timezone.localtime(exported_at).replace(tzinfo=None)).days


def shift_dates(rows, days):
    """Corre `days` días todas las fechas de las filas. Una hora sigue siendo la misma hora local:
    una lectura a las 19:00 sigue a las 19:00, también si entre medio cambió el horario."""
    if not days:
        return
    encoder = DjangoJSONEncoder()
    for row in rows:
        fields = row["fields"]
        for field in apps.get_model(row["model"])._meta.concrete_fields:
            value = fields.get(field.name)
            if value is None:
                continue
            if isinstance(field, models.DateTimeField):
                moved = timezone.localtime(parse_datetime(value)) + timedelta(days=days)
                fields[field.name] = encoder.default(moved)
            elif isinstance(field, models.DateField):
                fields[field.name] = (parse_date(value) + timedelta(days=days)).isoformat()


def rows_to_load(rows):
    """Las filas que `cargar` añade, y lo que deja fuera: las filas de modelos que no viajan (una
    copia puede traerlas) y las de BY_SLUG cuyo slug ya está en la base, como las páginas legales
    que crea `migrate`. Las de BY_SLUG entran sin clave."""
    labels = {label.lower(): label for label in MODELOS}
    kept, left = [], set()
    for row in rows:
        label = labels.get(row["model"])
        if label is None:
            left.add(row["model"])
            continue
        if label in BY_SLUG:
            row = {key: value for key, value in row.items() if key != "pk"}
            if apps.get_model(label).objects.filter(slug=row["fields"]["slug"]).exists():
                left.add(f"{row['model']} {row['fields']['slug']}")
                continue
        kept.append(row)
    return kept, sorted(left)


def clashes(rows):
    """Las filas cuya clave ya está en la base, por modelo: cargarlas las pisaría. El perfil del
    sitio no cuenta, porque su fila única se llena con la de la copia."""
    keys = defaultdict(set)
    for row in rows:
        label = apps.get_model(row["model"])._meta.label
        if "pk" in row and label not in FILLED_IN_PLACE:
            keys[label].add(row["pk"])
    found = {}
    for label, pks in keys.items():
        taken = sorted(
            apps.get_model(label).objects.filter(pk__in=pks).values_list("pk", flat=True)
        )
        if taken:
            found[label] = taken
    return found


class Command(DevelopmentCommand):
    help = "Carga, exporta o marca los datos de desarrollo (solo el contenido público)."

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
                "Falta decidir qué viaja (PUBLIC_ROWS, OWNED_ROWS, REFERENCED_ROWS, BY_SLUG, "
                f"PUBLIC_FIELDS, PRIVATE_FIELDS o IDENTITY_FIELDS): {'; '.join(problems)}"
            )
        if differences := identity.differences(SiteProfile.objects.filter(pk=1).first()):
            raise CommandError(
                "La identidad de esta base no es la de apps/devtools/identity.py, y la copia no "
                "la lleva: en otro equipo se vería otra. Iguálalas antes de exportar: "
                f"{'; '.join(differences)}"
            )
        included = exported_pks()
        objetos, datos = [], []
        for etiqueta in MODELOS:
            filas = list(
                apps.get_model(etiqueta).objects.filter(pk__in=included[etiqueta]).order_by("pk")
            )
            objetos.extend(filas)
            # Solo los campos de PUBLIC_FIELDS: lo privado, la identidad y lo que calcula la
            # base no se llegan a escribir.
            serialized = json.loads(
                serializers.serialize("json", filas, fields=sorted(PUBLIC_FIELDS[etiqueta]))
            )
            if etiqueta in BY_SLUG:
                for row in serialized:
                    del row["pk"]
            datos.extend(serialized)
        claves = {(obj._meta.label, obj.pk) for obj in objetos}
        for fila in datos:
            modelo = apps.get_model(fila["model"])
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
        copy = {
            "exported_at": DjangoJSONEncoder().default(timezone.now().replace(microsecond=0)),
            "objects": datos,
        }
        texto = json.dumps(copy, ensure_ascii=False, indent=1)
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
        ruta = CARPETA / "datos.json"
        if not ruta.exists():
            raise CommandError(f"No está {ruta}.")
        llenos = [e for e in CON_CONTENIDO if apps.get_model(e).objects.exists()]
        if llenos and DevelopmentMarker.is_marked():
            self.stdout.write(
                f"Esta base de desarrollo ya tiene contenido ({', '.join(llenos)}): no se carga "
                "nada. Para empezar de cero: docker compose down -v y vuelve a levantar."
            )
            return
        if llenos:
            raise CommandError(
                f"La base ya tiene contenido ({', '.join(llenos)}) y no está marcada como de "
                "desarrollo: no se pisa. Para empezar de cero: docker compose down -v y vuelve a "
                "levantar."
            )
        exported_at, rows = read_copy(ruta)
        rows, left_out = rows_to_load(rows)
        if taken := clashes(rows):
            raise CommandError(
                "La base ya tiene filas con las claves de la copia, y cargarla las pisaría: "
                + "; ".join(f"{label} {pks}" for label, pks in taken.items())
                + ". Si las crea una migración, ese modelo tiene que viajar por su slug (BY_SLUG)."
            )
        days = days_since(exported_at)
        shift_dates(rows, days)
        copiados = 0
        for archivo in sorted((CARPETA / "media").rglob("*")):
            nombre = archivo.relative_to(CARPETA / "media").as_posix()
            if archivo.is_file() and not default_storage.exists(nombre):
                with archivo.open("rb") as origen:
                    default_storage.save(nombre, File(origen))
                copiados += 1
        with tempfile.TemporaryDirectory() as folder:
            # loaddata reconoce el formato por la extensión.
            fixture = Path(folder) / "datos.json"
            fixture.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            with transaction.atomic():
                call_command("loaddata", str(fixture), verbosity=0)
                identity.apply(SiteProfile.load())
        call_command("generate_image_derivatives", verbosity=0)
        # La obra de la portada pide sus propias copias (AVIF y WebP), que hace SiteProfile al
        # guardarse. Se guardan solo esos campos: la fecha de actualización es la de la copia.
        SiteProfile.load().save(update_fields=["hero_image", "hero_image_phone"])
        DevelopmentMarker.mark()
        dates = (
            f"las fechas corridas {days} día{'' if days == 1 else 's'}"
            if exported_at
            else "las fechas tal cual (la copia no dice cuándo se exportó)"
        )
        self.stdout.write(
            f"Cargado: {copiados} archivos y {len(rows)} filas, con {dates}. "
            + (
                f"No se cargan, porque ya estaban o no viajan: {', '.join(left_out)}. "
                if left_out
                else ""
            )
            + "Crea tu cuenta para el panel con: python manage.py createsuperuser"
        )

    def marcar(self):
        DevelopmentMarker.mark()
        self.stdout.write("Base marcada como de desarrollo: ya se puede exportar desde aquí.")
