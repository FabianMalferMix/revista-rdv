"""Crea los grupos admin, editor y autor y les reparte los permisos de la matriz de roles
(apps/people/roles.py). Corre en cada release.

La sincronización es aditiva: añade lo que la matriz da y el grupo todavía no recibió, y nunca
restaura lo que el operador retiró a mano después (RoleGrant guarda lo ya repartido). La primera
vez que se sincroniza un grupo, sin ese registro, queda exactamente como dice la matriz; con
`--reset`, también, descartando los ajustes manuales.
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.people import roles
from apps.people.models import RoleGrant


class Command(BaseCommand):
    help = "Crea los grupos admin, editor y autor y sincroniza sus permisos con la matriz de roles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Deja cada grupo exactamente como dice la matriz. DESTRUCTIVO: descarta los "
                "permisos que se retiraron o se añadieron a mano desde el admin."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        totals = {}
        for role in (roles.ADMIN, roles.EDITOR, roles.AUTHOR):
            group, _ = Group.objects.get_or_create(name=role)
            wanted = list(roles.permissions_for(role))
            granted = set(
                RoleGrant.objects.filter(group=group).values_list("permission_id", flat=True)
            )
            if options["reset"] or not granted:
                group.permissions.set(wanted)
                RoleGrant.objects.filter(group=group).delete()
                RoleGrant.objects.bulk_create(
                    [RoleGrant(group=group, permission=perm) for perm in wanted]
                )
                self.stdout.write(f"  {role}: como dice la matriz.")
            else:
                new = [perm for perm in wanted if perm.pk not in granted]
                group.permissions.add(*new)
                RoleGrant.objects.bulk_create(
                    [RoleGrant(group=group, permission=perm) for perm in new]
                )
                current = set(group.permissions.values_list("pk", flat=True))
                withdrawn = [p for p in wanted if p.pk in granted and p.pk not in current]
                self.stdout.write(
                    f"  {role}: {len(new)} permisos nuevos de la matriz; se respetan "
                    f"{len(withdrawn)} retirados a mano."
                )
            totals[role] = group.permissions.count()
        if options["reset"]:
            self.stdout.write(
                self.style.WARNING("--reset: los tres grupos quedaron como dice la matriz.")
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Grupos listos — "
                + ", ".join(f"{role}: {count}" for role, count in totals.items())
                + " permisos."
            )
        )
