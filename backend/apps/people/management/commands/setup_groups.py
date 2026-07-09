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

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name="admin")
        editor_group, _ = Group.objects.get_or_create(name="editor")
        author_group, _ = Group.objects.get_or_create(name="autor")

        # admin: todos los permisos.
        admin_group.permissions.set(Permission.objects.all())

        # editor: todo lo de las apps del proyecto.
        editor_group.permissions.set(
            Permission.objects.filter(content_type__app_label__in=EDITOR_APPS)
        )

        # autor: conjunto acotado.
        author_perms = []
        for dotted in AUTHOR_PERMS:
            app_label, codename = dotted.split(".")
            perm = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()
            if perm:
                author_perms.append(perm)
        author_group.permissions.set(author_perms)

        self.stdout.write(
            self.style.SUCCESS(
                "Grupos listos — "
                f"admin: {admin_group.permissions.count()}, "
                f"editor: {editor_group.permissions.count()}, "
                f"autor: {author_group.permissions.count()} permisos."
            )
        )
