"""Retención de datos personales: purga lo que ya no hace falta conservar.

Minimización de datos (Ley 21.719). Cubre cuatro grupos:

  · suscriptores que nunca confirmaron (PENDING);
  · suscriptores DADOS DE BAJA — pedir la baja es pedir que dejemos de tratar los
    datos, así que conservarlos indefinidamente contradice lo que promete la política;
  · envíos ya resueltos (rechazados/retirados), con su adjunto privado;
  · registros de intentos de acceso de django-axes, que guardan direcciones IP y el
    usuario tecleado (ambos son datos personales) y no tenían ninguna caducidad.

Correr periódicamente (cron/beat) o a mano. `--days` fija la antigüedad mínima.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.submissions.models import Submission

# Los intentos de acceso se conservan bastante menos: su única utilidad es investigar
# un incidente reciente, y son PII (IP + usuario tecleado).
AXES_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = "Purga PII caducada: suscriptores, envíos resueltos e intentos de acceso."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=180, help="Antigüedad mínima (días).")
        parser.add_argument("--dry-run", action="store_true", help="Solo informa, no borra.")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        axes_cutoff = timezone.now() - timedelta(days=AXES_RETENTION_DAYS)

        pending = NewsletterSubscriber.objects.filter(
            status=NewsletterSubscriber.Status.PENDING, created_at__lt=cutoff
        )
        # La baja fija `status`, no una marca de tiempo propia: se usa `created_at` como
        # referencia conservadora (nunca borra antes de lo debido).
        unsubscribed = NewsletterSubscriber.objects.filter(
            status=NewsletterSubscriber.Status.UNSUBSCRIBED, created_at__lt=cutoff
        )
        resolved = Submission.objects.filter(
            status__in=[Submission.Status.REJECTED, Submission.Status.WITHDRAWN],
            created_at__lt=cutoff,
        )
        n_pending, n_unsub, n_subm = pending.count(), unsubscribed.count(), resolved.count()
        n_axes = self._axes_queryset(axes_cutoff)

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] se borrarían {n_pending} suscriptores PENDING, "
                f"{n_unsub} dados de baja, {n_subm} envíos y {n_axes['count']} intentos de acceso."
            )
            return

        files = 0
        for submission in resolved:
            if submission.file:
                submission.file.delete(save=False)  # borra el adjunto privado
                files += 1
        resolved.delete()
        pending.delete()
        unsubscribed.delete()
        for queryset in n_axes["querysets"]:
            queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Purgados: {n_pending} suscriptores PENDING, {n_unsub} dados de baja, "
                f"{n_subm} envíos ({files} adjuntos), {n_axes['count']} intentos de acceso."
            )
        )

    def _axes_queryset(self, cutoff):
        """Intentos de acceso de django-axes anteriores al corte.

        Se resuelve de forma perezosa: si axes no estuviera instalado, la purga del
        resto no debe romperse.
        """
        total, querysets = 0, []
        try:
            from axes.models import AccessAttempt, AccessFailureLog, AccessLog
        except ImportError:  # pragma: no cover
            return {"count": 0, "querysets": []}
        for modelo, campo in (
            (AccessAttempt, "attempt_time"),
            (AccessLog, "attempt_time"),
            (AccessFailureLog, "attempt_time"),
        ):
            qs = modelo.objects.filter(**{f"{campo}__lt": cutoff})
            total += qs.count()
            querysets.append(qs)
        return {"count": total, "querysets": querysets}
