from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Article, EditorialStatus


class LatestArticlesFeed(Feed):
    title = "Reseñas — Revista literaria"
    description = "Últimas reseñas, ensayos y entrevistas."
    link = "/"

    def items(self):
        return (
            Article.objects.filter(status=EditorialStatus.PUBLISHED)
            .select_related("section")
            .prefetch_related("authors")[:20]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.subtitle or item.excerpt

    def item_link(self, item):
        return reverse("content:article_detail", args=[item.slug])

    def item_pubdate(self, item):
        return item.published_at

    def item_author_name(self, item):
        names = [a.display_name for a in item.authors.all()]
        return ", ".join(names) if names else None

    def item_categories(self, item):
        return [item.section.name] if item.section else []
