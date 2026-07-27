from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work

from .models import Article, Collection, EditorialStatus, Page, Poem, PublishStatus, Section


class ArticleSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Article.objects.filter(status=EditorialStatus.PUBLISHED)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("content:article_detail", args=[obj.slug])


class SectionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Section.objects.all()

    def location(self, obj):
        return reverse("content:section_detail", args=[obj.slug])


class PoemSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Poem.objects.filter(status=EditorialStatus.PUBLISHED)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class CollectionSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Collection.objects.filter(status=PublishStatus.PUBLISHED)

    def location(self, obj):
        return reverse("content:collection_detail", args=[obj.slug])


class PageSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.3

    def items(self):
        return Page.objects.filter(status=PublishStatus.PUBLISHED)

    def location(self, obj):
        return reverse("content:page_detail", args=[obj.slug])


class MemberSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Contributor.members()

    def location(self, obj):
        return reverse("people:member_detail", args=[obj.slug])


class _ReviewsSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.4
    url_name = None

    def location(self, obj):
        return reverse(self.url_name, args=[obj.slug])


class WorkSitemap(_ReviewsSitemap):
    url_name = "reviews:work_detail"

    def items(self):
        return Work.objects.all()


class PublisherSitemap(_ReviewsSitemap):
    url_name = "reviews:publisher_detail"

    def items(self):
        return Publisher.objects.all()


class BookAuthorSitemap(_ReviewsSitemap):
    url_name = "reviews:bookauthor_detail"

    def items(self):
        return BookAuthor.objects.all()


SITEMAPS = {
    "articulos": ArticleSitemap,
    "poemas": PoemSitemap,
    "secciones": SectionSitemap,
    "colecciones": CollectionSitemap,
    "integrantes": MemberSitemap,
    "paginas": PageSitemap,
    "obras": WorkSitemap,
    "editoriales": PublisherSitemap,
    "autores": BookAuthorSitemap,
}
