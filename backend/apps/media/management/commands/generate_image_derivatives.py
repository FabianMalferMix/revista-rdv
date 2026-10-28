"""Genera los derivados de srcset de las imágenes existentes y les quita los metadatos que les
queden.

Idempotente: solo crea los derivados que faltan y solo reescribe las imágenes que traen
metadatos. Correrlo tras subir imágenes en masa, al desplegar un cambio que introduce o ajusta
los anchos de `MediaAsset.SRCSET_WIDTHS`, o para limpiar imágenes subidas antes de que la
limpieza fuera obligatoria. Sale con error si alguna imagen no se pudo limpiar (el log dice cuál
y por qué): habrá que reemplazarla.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.media.models import MediaAsset


class Command(BaseCommand):
    help = "Genera los derivados responsivos (srcset) de las imágenes y les quita los metadatos."

    def handle(self, *args, **options):
        total = 0
        unclean = []
        for asset in MediaAsset.objects.all().iterator():
            total += 1
            if not asset.strip_metadata():
                unclean.append(asset.pk)
            asset.ensure_derivatives()
        if unclean:
            raise CommandError(
                f"{len(unclean)} de {total} imágenes no se pudieron limpiar de metadatos "
                f"(recursos {', '.join(map(str, unclean))}): reemplázalas."
            )
        self.stdout.write(
            self.style.SUCCESS(f"Derivados verificados y metadatos limpios en {total} recursos.")
        )
