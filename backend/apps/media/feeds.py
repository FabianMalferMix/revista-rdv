"""Feed podcast: registros de audio publicados, con namespace iTunes.

El generador declara `xmlns:itunes` y emite las etiquetas de canal e ítem que se
pueden derivar del SiteProfile (author/summary/explicit/category). Para envío a
Apple Podcasts falta `itunes:image` con URL ABSOLUTA a una portada cuadrada
(≥1400px): requiere un asset dedicado del colectivo, no se fuerza aquí.
"""

import mimetypes

from django.contrib.syndication.views import Feed
from django.db.models import F
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed

from config.feeds import stable_guid
from config.origin import absolute_url

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
    """El pódcast de los registros.

    No guarda nada de la petición: las URL absolutas salen de SITE_URL (config/origin.py),
    así que una sola instancia sirve a todos los hilos de gunicorn.
    """

    feed_type = PodcastFeed
    description = "Registros en audio de lecturas y recitales."

    def _perfil(self):
        from apps.showcase.models import SiteProfile

        return SiteProfile.load()

    def title(self):
        return f"{self._perfil().name} — Registros"

    def link(self):
        return absolute_url(reverse("media:recording_index"))

    def feed_url(self):
        return absolute_url(reverse("recordings_feed"))

    def feed_extra_kwargs(self, obj):
        p = self._perfil()
        return {
            "itunes_author": p.name,
            "itunes_summary": p.tagline or self.description,
            "itunes_explicit": "false",
            "itunes_category": "Arts",
        }

    def item_extra_kwargs(self, item):
        return {"itunes_summary": item.description or item.get_kind_display()}

    def items(self):
        return (
            Recording.objects.published()
            .filter(kind=Recording.Kind.AUDIO)
            .order_by(F("published_at").desc(nulls_last=True), "-created_at")[:20]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.description or item.get_kind_display()

    def item_link(self, item):
        return absolute_url(item.get_absolute_url())

    # El GUID no es la dirección: no cambia con el slug ni con el dominio, y una
    # aplicación de pódcast no vuelve a descargar el episodio.
    item_guid_is_permalink = False

    def item_guid(self, item):
        return stable_guid("recording", item.pk)

    def item_pubdate(self, item):
        return item.published_at

    # Enclosure solo para registros con archivo propio (los embeds van como enlace).
    def item_enclosure_url(self, item):
        # URL ABSOLUTA: los clientes de podcast exigen que el enclosure sea resoluble; una
        # URL relativa deja el episodio sin audio en Apple/Spotify.
        return absolute_url(item.file.url) if item.file else None

    def item_enclosure_length(self, item):
        try:
            return item.file.size if item.file else None
        except OSError:
            return 0

    def item_enclosure_mime_type(self, item):
        if not item.file:
            return None
        return mimetypes.guess_type(item.file.name)[0] or "audio/mpeg"
