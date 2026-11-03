from celery import shared_task
from django.core.management import call_command
from django.db import OperationalError


# Una base que no responde se reintenta: la purga es idempotente. Un fallo de otra clase (un
# adjunto que no se pudo borrar) termina la tarea en error, con la causa en el log.
@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def purge_stale_pii():
    """Purga periódica de datos personales caducados (minimización de datos).

    Envuelve el comando `purge_stale_data` para poder programarlo en Celery beat:
    elimina suscriptores nunca confirmados y envíos resueltos con su adjunto.
    """
    call_command("purge_stale_data")
