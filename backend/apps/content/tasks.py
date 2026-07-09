from celery import shared_task
from django.utils import timezone


@shared_task
def publish_due_articles():
    """Publica los artículos programados cuya fecha ya venció. Corre cada minuto."""
    from .models import Article, ArticleStatus, EditorialTransition

    due = list(
        Article.objects.filter(
            status=ArticleStatus.SCHEDULED, published_at__lte=timezone.now()
        )
    )
    for article in due:
        article.status = ArticleStatus.PUBLISHED
        article.save(update_fields=["status", "updated_at"])
        EditorialTransition.objects.create(
            article=article,
            from_status=ArticleStatus.SCHEDULED,
            to_status=ArticleStatus.PUBLISHED,
            note="Publicación automática programada",
        )
    return len(due)
