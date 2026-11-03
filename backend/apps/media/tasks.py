from celery import shared_task

from . import services


# Una portada de 40 megapíxeles con sus doce copias tarda unos segundos en un núcleo: el límite
# blando general (30 s) se queda corto. Un fallo del disco o del almacenamiento se reintenta; un
# archivo ilegible no, porque no cambia (el servicio lo registra y devuelve False).
@shared_task(
    soft_time_limit=120,
    time_limit=150,
    autoretry_for=(OSError,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def process_image(asset_id):
    """Las copias del `srcset`, las de la portada y el color del borde de una imagen.

    Recibe solo el id. Es idempotente: un reintento o una segunda tarea para el mismo recurso
    solo hacen lo que falta.
    """
    services.process_image(asset_id)
