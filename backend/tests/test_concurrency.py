"""Concurrencia e idempotencia REALES (hallazgo del crítico de completitud).

CELERY_TASK_ALWAYS_EAGER hace que la suite normal nunca ejecute los caminos
concurrentes que se endurecieron en f2-3/f2-4 (lock de fila + re-verificación de
estado). Estos tests usan transaction=True (transacciones reales, sin el rollback
por test) e hilos con conexiones independientes, y afirman el INVARIANTE del
resultado (exactamente una publicación / transición / fila), que se cumple
independientemente del entrelazado de los hilos — por eso no son flaky.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.content.models import Article, EditorialStatus, EditorialTransition
from apps.content.tasks import publish_due_items
from apps.content.workflow import perform_transition


def _run_concurrently(fn, n):
    """Ejecuta fn() en n hilos a la vez (barrera para maximizar la contención).
    Devuelve (resultados, errores) por índice; cada hilo cierra su conexión."""
    barrier = threading.Barrier(n)
    results = [None] * n
    errors = [None] * n

    def worker(i):
        barrier.wait()
        try:
            results[i] = fn()
        except Exception as exc:  # noqa: BLE001 — se inspecciona en la aserción
            errors[i] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, errors


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_publish_due_items_is_idempotent_under_concurrency(make_article):
    """Cuatro corridas simultáneas de publish_due_items sobre la misma pieza vencida
    publican exactamente una vez y registran una sola transición (sin doble beat)."""
    art = make_article(
        slug="programada",
        status=EditorialStatus.SCHEDULED,
        published_at=timezone.now() - timedelta(minutes=1),
    )
    results, errors = _run_concurrently(publish_due_items, 4)

    assert errors == [None] * 4, errors
    art.refresh_from_db()
    assert art.status == EditorialStatus.PUBLISHED
    assert EditorialTransition.objects.filter(to_status=EditorialStatus.PUBLISHED).count() == 1
    assert sum(r for r in results if r) == 1  # solo un hilo contabilizó la publicación


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_perform_transition_serializes_concurrent_publish(make_article, editor):
    """Dos editores publicando la misma pieza a la vez: uno gana, el otro ve el estado
    ya cambiado bajo lock y falla con ValueError. Una sola transición registrada."""
    art = make_article(slug="aprobada", status=EditorialStatus.APPROVED)

    def do():
        fresh = Article.objects.get(pk=art.pk)  # estado en memoria por hilo
        return perform_transition(fresh, "publish", editor)

    results, errors = _run_concurrently(do, 2)

    art.refresh_from_db()
    assert art.status == EditorialStatus.PUBLISHED
    assert EditorialTransition.objects.filter(to_status=EditorialStatus.PUBLISHED).count() == 1
    failures = [e for e in errors if e is not None]
    assert len(failures) == 1 and isinstance(failures[0], ValueError), errors


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_subscribe_same_email_stays_unique_under_concurrency():
    """Cinco altas simultáneas del mismo email dejan exactamente una fila: el UNIQUE
    + get_or_create absorben la IntegrityError de la carrera (una sola creación)."""
    from apps.community.models import NewsletterSubscriber

    def do():
        _, created = NewsletterSubscriber.objects.get_or_create(email="carrera@example.com")
        return created

    results, errors = _run_concurrently(do, 5)

    assert errors == [None] * 5, errors  # get_or_create no propaga la IntegrityError
    assert NewsletterSubscriber.objects.filter(email="carrera@example.com").count() == 1
    assert sum(1 for r in results if r) == 1  # exactamente un hilo creó la fila
