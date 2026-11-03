"""Las comprobaciones de /readyz/ y el latido de las tareas.

/readyz/ lo consulta el monitor externo cada pocos minutos: responde 200 solo si el sitio
puede operar, y 503 con la lista de lo que falla. Cada comprobación que falla deja su causa
en el log, porque el monitor solo ve el código.

El latido: `publish_due_items`, que beat despacha cada minuto y el worker ejecuta, guarda la
hora en el Redis del broker, que comparten la web, el worker y beat. Si tiene más de cinco
minutos, beat, el worker o el broker entre ellos dejaron de funcionar, aunque los tres
procesos sigan vivos.
"""

import logging
import shutil
import time
from datetime import timedelta
from pathlib import Path

import redis
from django.conf import settings
from django.db import DatabaseError, connections
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

logger = logging.getLogger(__name__)

HEARTBEAT_KEY = "resenas:latido:publicar-programadas"
HEARTBEAT_MAX_AGE = 5 * 60  # segundos: cinco corridas perdidas
# Una pieza programada que venció hace más que esto delata que la publicación no corre.
OVERDUE_GRACE = timedelta(minutes=5)
# Fracción libre mínima del disco de los medios públicos y privados.
MIN_FREE_DISK = 0.05


def _broker():
    return redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=3, socket_timeout=3)


def record_heartbeat():
    """Lo llama publish_due_items al terminar cada corrida."""
    try:
        _broker().set(HEARTBEAT_KEY, int(time.time()), ex=24 * 3600)
    except redis.RedisError as exc:
        # Sin broker la tarea tampoco habría llegado al worker: el latido envejece solo y
        # /readyz/ lo dirá.
        logger.warning("No se pudo guardar el latido de las tareas: %s", exc)


def check_database():
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as exc:
        return f"la base de datos no responde: {exc}"
    return None


def check_broker():
    try:
        _broker().ping()
    except redis.RedisError as exc:
        return f"el broker (Redis) no responde: {exc}"
    return None


def check_heartbeat():
    try:
        value = _broker().get(HEARTBEAT_KEY)
    except redis.RedisError as exc:
        return f"no se pudo leer el latido de las tareas: {exc}"
    if value is None:
        return "las tareas no han dejado latido: beat o el worker no están corriendo"
    age = time.time() - int(value)
    if age > HEARTBEAT_MAX_AGE:
        return f"el último latido de las tareas es de hace {int(age // 60)} min: beat o el worker se pararon"
    return None


def check_cache():
    from config.cache import cache_ping

    reason = cache_ping()
    return f"la caché (Redis) no responde: {reason}" if reason else None


def check_scheduled():
    from apps.content.models import EditorialStatus, editorial_models

    limit = timezone.now() - OVERDUE_GRACE
    try:
        overdue = sum(
            model.objects.filter(status=EditorialStatus.SCHEDULED, published_at__lt=limit).count()
            for model in editorial_models()
        )
    except DatabaseError as exc:
        return f"no se pudieron contar las piezas programadas: {exc}"
    if overdue:
        return f"{overdue} pieza(s) programada(s) vencida(s) sin publicar"
    return None


def check_migrations():
    try:
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except DatabaseError as exc:
        return f"no se pudieron leer las migraciones aplicadas: {exc}"
    if plan:
        return f"{len(plan)} migración(es) sin aplicar"
    return None


def _existing(path):
    """La carpeta, o la primera que exista hacia arriba: el disco donde se crearía."""
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def check_disk():
    for root in dict.fromkeys([settings.MEDIA_ROOT, settings.PRIVATE_MEDIA_ROOT]):
        try:
            usage = shutil.disk_usage(_existing(root))
        except OSError as exc:
            return f"no se pudo medir el disco de {root}: {exc}"
        if usage.free / usage.total < MIN_FREE_DISK:
            return f"queda menos del {MIN_FREE_DISK * 100:.0f} % libre en el disco de {root}"
    return None


CHECKS = {
    "database": check_database,
    "broker": check_broker,
    "cache": check_cache,
    "heartbeat": check_heartbeat,
    "scheduled": check_scheduled,
    "migrations": check_migrations,
    "disk": check_disk,
}


def readiness():
    """{comprobación: True | False}. Lo que falla queda en el log con su causa: lo esperado
    (un servicio caído), como WARNING; un fallo de la propia comprobación, con su traza."""
    results = {}
    for name, check in CHECKS.items():
        try:
            reason = check()
        except Exception:
            logger.exception("readyz: la comprobación %s falló de forma inesperada", name)
            results[name] = False
            continue
        if reason:
            logger.warning("readyz: %s", reason)
        results[name] = reason is None
    return results
