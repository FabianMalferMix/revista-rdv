"""Retención de datos personales: purga lo que ya no hace falta conservar.

Minimización de datos (Ley 21.719): elimina suscriptores que nunca confirmaron y
envíos ya resueltos (rechazados/retirados) más antiguos que --days, borrando también
el adjunto privado. Correr periódicamente (cron/beat) o a mano.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.submissions.models import Submission


class Command(BaseCommand):
    help = "Purga PII caducada: suscriptores nunca confirmados y envíos resueltos."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=180, help="Antigüedad mínima (días).")
        parser.add_argument("--dry-run", action="store_true", help="Solo informa, no borra.")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])

        pending = NewsletterSubscriber.objects.filter(
            status=NewsletterSubscriber.Status.PENDING, created_at__lt=cutoff
        )
        resolved = Submission.objects.filter(
            status__in=[Submission.Status.REJECTED, Submission.Status.WITHDRAWN],
            created_at__lt=cutoff,
        )
        n_subs, n_subm = pending.count(), resolved.count()

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] se borrarían {n_subs} suscriptores PENDING y {n_subm} envíos."
            )
            return

        files = 0
        for submission in resolved:
            if submission.file:
                submission.file.delete(save=False)  # borra el adjunto privado
                files += 1
        resolved.delete()
        pending.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Purgados: {n_subs} suscriptores PENDING, {n_subm} envíos ({files} adjuntos)."
            )
        )
