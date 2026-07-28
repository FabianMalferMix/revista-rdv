"""Feed podcast: registros de audio publicados, con namespace iTunes.

El generador declara `xmlns:itunes` y emite las etiquetas de canal e ítem que se
pueden derivar del SiteProfile (author/summary/explicit/category). Para envío a
Apple Podcasts falta `itunes:image` con URL ABSOLUTA a una portada cuadrada
(≥1400px): requiere un asset dedicado del colectivo, no se fuerza aquí.
"""

import mimetypes

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Rss201rev2Feed

from .models import Recording


class PodcastFeed(Rss201rev2Feed):
    """RSS 2.0 con el namespace y las etiquetas mínimas de iTunes."""

    def rss_attributes(self):
        attrs = super().rss_attributes()
        attrs["xmlns:itunes"] = "http://www.itunes.com/dtds/podcast-1.0.dtd"
        return attrs

    def add_root_elements(self, handler):
        super().add_root_elements(handler)
        if self.feed.get("itunes_author"):
            handler.addQuickElement("itunes:author", self.feed["itunes_author"])
        if self.feed.get("itunes_summary"):
            handler.addQuickElement("itunes:summary", self.feed["itunes_summary"])
        handler.addQuickElement("itunes:explicit", self.feed.get("itunes_explicit") or "false")
        handler.addQuickElement(
            "itunes:category", "", {"text": self.feed.get("itunes_category") or "Arts"}
        )

    def add_item_elements(self, handler, item):
        super().add_item_elements(handler, item)
        if item.get("itunes_summary"):
            handler.addQuickElement("itunes:summary", item["itunes_summary"])
        handler.addQuickElement("itunes:episodeType", "full")


class RecordingsFeed(Feed):
    feed_type = PodcastFeed
    title = "Registros — lecturas del colectivo"
    link = "/registros/"
    description = "Registros en audio de lecturas y recitales."

    def feed_extra_kwargs(self, obj):
        from apps.showcase.models import SiteProfile

        p = SiteProfile.load()
        return {
            "itunes_author": p.name,
            "itunes_summary": p.tagline or self.description,
            "itunes_explicit": "false",
            "itunes_category": "Arts",
        }

    def item_extra_kwargs(self, item):
        return {"itunes_summary": item.description or item.get_kind_display()}

    def items(self):
        return Recording.objects.filter(published=True, kind=Recording.Kind.AUDIO).order_by(
            "-published_at", "-created_at"
        )[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.description or item.get_kind_display()

    def item_link(self, item):
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.published_at

    # Enclosure solo para registros con archivo propio (los embeds van como enlace).
    def item_enclosure_url(self, item):
        return item.file.url if item.file else None

    def item_enclosure_length(self, item):
        try:
            return item.file.size if item.file else None
        except OSError:
            return 0

    def item_enclosure_mime_type(self, item):
        if not item.file:
            return None
        return mimetypes.guess_type(item.file.name)[0] or "audio/mpeg"
