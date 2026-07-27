from celery import shared_task
from django.utils import timezone


@shared_task
def publish_due_items():
    """Publica artículos y poemas programados cuya fecha ya venció. Corre cada minuto."""
    from .models import Article, EditorialStatus, EditorialTransition, Poem

    published = 0
    for model in (Article, Poem):
        due = list(
            model.objects.filter(status=EditorialStatus.SCHEDULED, published_at__lte=timezone.now())
        )
        for item in due:
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
