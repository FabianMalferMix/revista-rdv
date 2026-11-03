"""Retención de datos personales: purga lo que ya no hace falta conservar.

Minimización de datos (Ley 21.719). Cubre cuatro grupos:

  · suscriptores que nunca confirmaron (PENDING);
  · suscriptores DADOS DE BAJA — pedir la baja es pedir que dejemos de tratar los
    datos, así que conservarlos indefinidamente contradice lo que promete la política;
  · envíos ya resueltos (rechazados/retirados), con su adjunto privado;
  · registros de intentos de acceso de django-axes, que guardan direcciones IP y el
    usuario tecleado (ambos son datos personales) y no tenían ninguna caducidad.

Correr periódicamente (cron/beat) o a mano. `--days` fija la antigüedad mínima.

Cada grupo se purga por separado: si uno falla, los demás se purgan igual, y el comando sale
con error al final. Los adjuntos los borra la señal de apps.media.filecleanup al confirmar;
uno que siga en el disco cuenta como fallo.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, transaction
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.submissions.models import Submission

logger = logging.getLogger(__name__)

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

        # Cada uno, desde su último cambio de estado: quien vuelve a suscribirse empieza de
        # nuevo, y un envío rechazado hoy no se borra por haber llegado hace meses.
        pending = NewsletterSubscriber.objects.filter(
            status=NewsletterSubscriber.Status.PENDING, status_changed_at__lt=cutoff
        )
        unsubscribed = NewsletterSubscriber.objects.filter(
            status=NewsletterSubscriber.Status.UNSUBSCRIBED, status_changed_at__lt=cutoff
        )
        resolved = Submission.objects.filter(status__in=Submission.RESOLVED, resolved_at__lt=cutoff)
        n_pending, n_unsub, n_subm = pending.count(), unsubscribed.count(), resolved.count()
        n_axes = self._axes_queryset(axes_cutoff)

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] se borrarían {n_pending} suscriptores PENDING, "
                f"{n_unsub} dados de baja, {n_subm} envíos y {n_axes['count']} intentos de acceso."
            )
            return

        attachments = [(sub.pk, sub.file.storage, sub.file.name) for sub in resolved if sub.file]
        left = []

        def check_attachments():
            # Después de que la señal intente borrarlos: los que siguen no se pudieron borrar, y
            # el ERROR de filecleanup dice por qué.
            left.extend(pk for pk, storage, name in attachments if storage.exists(name))

        groups = [
            ("envíos resueltos", resolved),
            ("suscriptores pendientes", pending),
            ("suscriptores dados de baja", unsubscribed),
            *(
                (f"registros de axes ({queryset.model.__name__})", queryset)
                for queryset in n_axes["querysets"]
            ),
        ]
        errors = []
        for label, queryset in groups:
            try:
                queryset.delete()
            except Exception as exc:
                logger.exception("La purga de %s falló", label)
                errors.append((label, exc))
            else:
                if queryset is resolved:
                    transaction.on_commit(check_attachments)
        if left:
            errors.append((f"{len(left)} adjuntos (envíos {', '.join(map(str, left))})", None))

        if errors:
            # Una base que no responde se reintenta (la purga es idempotente); el resto se arregla
            # a mano.
            transient = next((e for _, e in errors if isinstance(e, OperationalError)), None)
            if transient is not None:
                raise transient
            raise CommandError(
                "La purga no terminó: " + "; ".join(label for label, _ in errors) + ". "
                "El log dice por qué."
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Purgados: {n_pending} suscriptores PENDING, {n_unsub} dados de baja, "
                f"{n_subm} envíos ({len(attachments)} adjuntos), {n_axes['count']} intentos de "
                "acceso."
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
