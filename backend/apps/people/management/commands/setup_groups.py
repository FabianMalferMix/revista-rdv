"""Crea los grupos admin/editor/autor y les asigna permisos.

Idempotente: se puede correr en cada arranque (lo hace el entrypoint).
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

# El editor recibe todos los permisos de estas apps del proyecto.
EDITOR_APPS = ["content", "community", "reviews", "submissions", "media", "people"]

# El autor recibe un conjunto acotado (crear/editar sus artículos y el catálogo).
AUTHOR_PERMS = [
    "content.add_article",
    "content.change_article",
    "content.view_article",
    "content.view_section",
    "content.view_tag",
    "reviews.add_work",
    "reviews.change_work",
    "reviews.view_work",
    "reviews.add_publisher",
    "reviews.view_publisher",
    "reviews.add_bookauthor",
    "reviews.view_bookauthor",
    "media.add_mediaasset",
    "media.view_mediaasset",
    "people.view_contributor",
]


class Command(BaseCommand):
    help = "Crea los grupos admin/editor/autor y asigna sus permisos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Reemplaza los permisos del grupo en vez de añadirlos. DESTRUCTIVO: "
                "descarta cualquier ajuste hecho a mano desde el admin."
            ),
        )

    def handle(self, *args, **options):
        # SIEMBRA, no sincronización (hallazgo S-12). El entrypoint ejecuta este comando
        # en CADA arranque y usaba `.set()`, así que cualquier permiso retirado a mano
        # desde el admin —por ejemplo, quitarle a un editor la capacidad de borrar envíos
        # tras un incidente— reaparecía en el siguiente despliegue, en silencio.
        #
        # OJO: pasar de `set()` a `add()` NO basta, porque vuelve a añadir el conjunto
        # entero y con él el permiso retirado. La única forma de respetar una decisión del
        # operador es no tocar un grupo ya configurado: se siembra cuando el grupo se
        # acaba de crear o está vacío, y se reemplaza solo con --reset (que el entrypoint
        # no usa).
        reset = options["reset"]

        admin_group, admin_nuevo = Group.objects.get_or_create(name="admin")
        editor_group, editor_nuevo = Group.objects.get_or_create(name="editor")
        author_group, autor_nuevo = Group.objects.get_or_create(name="autor")

        # autor: conjunto acotado.
        author_perms = []
        for dotted in AUTHOR_PERMS:
            app_label, codename = dotted.split(".")
            perm = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()
            if perm:
                author_perms.append(perm)

        resultados = {
            "admin": self._sembrar(
                admin_group, Permission.objects.all(), reset=reset, nuevo=admin_nuevo
            ),
            "editor": self._sembrar(
                editor_group,
                Permission.objects.filter(content_type__app_label__in=EDITOR_APPS),
                reset=reset,
                nuevo=editor_nuevo,
            ),
            "autor": self._sembrar(author_group, author_perms, reset=reset, nuevo=autor_nuevo),
        }

        for nombre, que_paso in resultados.items():
            if que_paso == "conservados":
                self.stdout.write(
                    f"  {nombre}: ya configurado; se conservan sus permisos "
                    f"(--reset para reemplazarlos)."
                )
        if reset:
            self.stdout.write(
                self.style.WARNING("--reset: se reemplazaron los permisos de los tres grupos.")
            )

        self._resumen(admin_group, editor_group, author_group)

    @staticmethod
    def _sembrar(group, perms, *, reset, nuevo):
        """Asigna los permisos solo si procede. Devuelve qué se hizo."""
        if reset:
            group.permissions.set(perms)
            return "reemplazados"
        if nuevo or not group.permissions.exists():
            group.permissions.set(perms)
            return "sembrados"
        return "conservados"

    def _resumen(self, admin_group, editor_group, author_group):
        self.stdout.write(
            self.style.SUCCESS(
                "Grupos listos — "
                f"admin: {admin_group.permissions.count()}, "
                f"editor: {editor_group.permissions.count()}, "
                f"autor: {author_group.permissions.count()} permisos."
            )
        )
