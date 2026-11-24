from celery import shared_task
from django.core.management import call_command
from django.db import OperationalError


# Corre una vez por semana y borra en bloque: si se corta, lo caducado se queda hasta la semana
# siguiente, así que tiene más margen que la publicación, que corre cada minuto. Una base que no
# responde se reintenta: la purga es idempotente. Un fallo de otra clase (un adjunto que no se
# pudo borrar) termina la tarea en error, con la causa en el log.
@shared_task(
    soft_time_limit=120,
    time_limit=150,
    autoretry_for=(OperationalError,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def purge_stale_pii():
    """Purga periódica de datos personales caducados (minimización de datos).

    Envuelve el comando `purge_stale_data` para poder programarlo en Celery beat:
    elimina suscriptores nunca confirmados o dados de baja, envíos resueltos con su
    adjunto y los registros de acceso de django-axes.
    """
    call_command("purge_stale_data")
