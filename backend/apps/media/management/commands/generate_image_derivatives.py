"""Genera los derivados de srcset para las imágenes existentes.

Idempotente (solo crea los que faltan). Correrlo tras subir imágenes en masa o al
desplegar un cambio que introduce/ajusta los anchos de `MediaAsset.SRCSET_WIDTHS`.
"""

from django.core.management.base import BaseCommand

from apps.media.models import MediaAsset


class Command(BaseCommand):
    help = "Genera los derivados responsivos (srcset) de todas las imágenes."

    def handle(self, *args, **options):
        n = 0
        for asset in MediaAsset.objects.all().iterator():
            asset.ensure_derivatives()
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Derivados verificados para {n} recursos."))
