from celery import shared_task
from django.db import OperationalError
from django.utils import timezone


@shared_task(
    acks_late=True,  # confirma al terminar: si cae el worker entero, Redis la reentrega
    autoretry_for=(OperationalError,),  # reintenta errores transitorios de BD
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def publish_due_items():
    """Publica las piezas programadas cuya fecha ya venció. Corre cada minuto.

    Pasa por `perform_transition`, como la publicación manual, con el actor de sistema: misma
    bitácora, mismas reglas de fecha y mismo bloqueo de fila. Es idempotente: la transición
    vuelve a leer cada pieza bajo bloqueo y no hace nada si ya dejó de estar programada, así
    que un doble beat, un reintento, una reentrega tras caer el worker o una acción manual
    concurrente no duplican la publicación ni la bitácora.
    """
    from .models import EditorialStatus, editorial_models
    from .workflow import SYSTEM, perform_transition

    published = 0
    for model in editorial_models():
        due = model.objects.filter(
            status=EditorialStatus.SCHEDULED, published_at__lte=timezone.now()
        )
        for item in due:
            try:
                perform_transition(item, "publish", SYSTEM, note="Publicación programada.")
            except ValueError:
                continue  # ya la movió otra corrida o una acción manual
            published += 1
    return published
