"""Procesa las imágenes existentes con el mismo servicio que las recién subidas.

Limpia de metadatos las que aún no se comprobaron, genera las copias que falten (`srcset` y, si
la imagen es la portada, sus copias AVIF y WebP), repara el ancho y el alto y mide el color del
borde. Idempotente: solo abre las imágenes a las que les falta algo. Correrlo tras subir
imágenes en masa, al desplegar un cambio que introduce o ajusta los anchos de las copias, o para
limpiar imágenes subidas antes de que la limpieza fuera obligatoria. Sale con error si alguna
imagen no se pudo limpiar o leer (el log dice cuál y por qué): habrá que reemplazarla.
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from apps.media.models import MediaAsset
from apps.media.services import process_image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Limpia de metadatos las imágenes, genera sus copias (srcset y portada) y mide el color "
        "de su borde."
    )

    def handle(self, *args, **options):
        ids = list(MediaAsset.objects.order_by("pk").values_list("pk", flat=True))
        failed = []
        for pk in ids:
            # Un recurso que falla de una manera inesperada no detiene a los demás.
            try:
                ok = process_image(pk)
            except Exception:
                logger.exception("No se pudo procesar la imagen del recurso %s", pk)
                ok = False
            if not ok:
                failed.append(pk)
        if failed:
            raise CommandError(
                f"{len(failed)} de {len(ids)} imágenes no se pudieron limpiar o leer "
                f"(recursos {', '.join(map(str, failed))}): reemplázalas."
            )
        self.stdout.write(self.style.SUCCESS(f"{len(ids)} imágenes procesadas."))
