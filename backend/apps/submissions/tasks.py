from celery import shared_task
from django.core.management import call_command


@shared_task
def purge_stale_pii():
    """Purga periódica de datos personales caducados (minimización de datos).

    Envuelve el comando `purge_stale_data` para poder programarlo en Celery beat:
    elimina suscriptores nunca confirmados y envíos resueltos con su adjunto.
    """
    call_command("purge_stale_data")
