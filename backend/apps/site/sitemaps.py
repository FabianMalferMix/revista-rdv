"""El sitemap del sitio: la portada, los índices y las fichas."""

from django.urls import reverse

from apps.agenda.models import Event
from apps.content.models import Article, Collection, Page, Poem, Section
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from apps.showcase.models import Publication
from config.origin import FixedOriginSitemap as Sitemap


class StaticViewSitemap(Sitemap):
    """La portada y los índices: las páginas estables, sin modelo detrás."""

    changefreq = "weekly"

    # Nombres de URL de las landing públicas y estables.
    _views = [
        "site:home",
        "content:text_archive",
        "content:poem_index",
        "content:collection_index",
        "people:member_index",
        "agenda:agenda",
        "agenda:trayectoria",
        "agenda:gallery",
        "media:recording_index",
        "showcase:publication_index",
        "showcase:press_index",
        "showcase:partner_index",
        "showcase:dossier",
    ]

    def items(self):
        return self._views

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == "site:home" else 0.6


class TimestampedSitemap(Sitemap):
    """Las fichas que guardan cuándo se editaron (config.models.TimestampedModel): `lastmod` es
    la última edición."""

    def lastmod(self, obj):
        return obj.updated_at


# Las secciones de fichas no redefinen `location`: la dirección de cada pieza es la de su
# `get_absolute_url`. Cada una trae solo lo que leen esa dirección y `lastmod` (`only`): las filas
# enteras llevan el cuerpo de cada texto.


class ArticleSitemap(TimestampedSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Article.objects.published().only("slug", "updated_at")


class SectionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Section.objects.only("slug")


class PoemSitemap(TimestampedSitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Poem.objects.published().only("slug", "updated_at")


class CollectionSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Collection.objects.published().only("slug")


class PageSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.3

    def items(self):
        return Page.objects.published().only("slug")


class EventSitemap(TimestampedSitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Event.objects.published().only("slug", "updated_at")


class PublicationSitemap(TimestampedSitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Publication.objects.published().only("slug", "updated_at")


class RecordingSitemap(TimestampedSitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return Recording.objects.published().only("slug", "updated_at")


class MemberSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Contributor.objects.members().select_related(None).only("slug", "is_member")


class CollaboratorSitemap(Sitemap):
    """Las personas de fuera del colectivo con obra publicada: las que tienen ficha."""

    changefreq = "monthly"
    priority = 0.4

    def items(self):
        return (
            Contributor.objects.visible()
            .filter(is_member=False)
            .order_by("display_name")
            .only("slug", "is_member")
        )


class _ReviewsSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.4


class WorkSitemap(_ReviewsSitemap):
    def items(self):
        return Work.objects.visible().only("slug")


class PublisherSitemap(_ReviewsSitemap):
    def items(self):
        return Publisher.objects.visible().only("slug")


class BookAuthorSitemap(_ReviewsSitemap):
    def items(self):
        return BookAuthor.objects.visible().only("slug")


SITEMAPS = {
    "estaticas": StaticViewSitemap,
    "articulos": ArticleSitemap,
    "poemas": PoemSitemap,
    "secciones": SectionSitemap,
    "colecciones": CollectionSitemap,
    "integrantes": MemberSitemap,
    "colaboradores": CollaboratorSitemap,
    "eventos": EventSitemap,
    "registros": RecordingSitemap,
    "publicaciones": PublicationSitemap,
    "paginas": PageSitemap,
    "obras": WorkSitemap,
    "editoriales": PublisherSitemap,
    "autores": BookAuthorSitemap,
}

# Las fichas públicas que el sitemap no anuncia, con su motivo. Toda ficha está en SITEMAPS o
# aquí (tests/test_completeness.py).
EXCLUDED_FROM_SITEMAP = {
    "content:tag_detail": "Listados de los textos de una etiqueta: repiten fichas que ya están.",
}
