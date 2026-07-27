from celery import shared_task
from django.db import OperationalError, transaction
from django.utils import timezone


@shared_task(
    acks_late=True,  # el ack va tras completar: si el worker muere, se re-encola
    autoretry_for=(OperationalError,),  # reintenta errores transitorios de BD
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def publish_due_items():
    """Publica artículos y poemas programados cuya fecha ya venció. Corre cada minuto.

    Idempotente: re-lee cada pieza bajo lock de fila y solo publica si sigue
    SCHEDULED, así un doble beat, un reintento (acks_late) o una acción manual
    concurrente no duplican la publicación ni la bitácora.
    """
    from .models import Article, EditorialStatus, EditorialTransition, Poem

    published = 0
    for model in (Article, Poem):
        due_ids = list(
            model.objects.filter(
                status=EditorialStatus.SCHEDULED, published_at__lte=timezone.now()
            ).values_list("pk", flat=True)
        )
        for pk in due_ids:
            with transaction.atomic():
                # Lock por fila + re-verificación del estado: cierra el TOCTOU.
                item = (
                    model.objects.select_for_update()
                    .filter(pk=pk, status=EditorialStatus.SCHEDULED)
                    .first()
                )
                if item is None:
                    continue  # ya lo publicó otra corrida/acción: nada que hacer
                item.status = EditorialStatus.PUBLISHED
                item.save(update_fields=["status", "updated_at"])
                EditorialTransition.objects.create(
                    item=item,
                    from_status=EditorialStatus.SCHEDULED,
                    to_status=EditorialStatus.PUBLISHED,
                    note="Publicación automática programada",
                )
                published += 1
    return published
