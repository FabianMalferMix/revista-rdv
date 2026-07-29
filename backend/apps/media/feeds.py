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

    def get_feed(self, obj, request):
        # Capturamos la request para construir la URL ABSOLUTA del enclosure: Django solo
        # aplica add_domain a los <link>, no al <enclosure>, y `item_enclosure_url` no
        # recibe la request.
        #
        # Guardarlo en `self` solo es seguro si la instancia NO se comparte. Lo era
        # mientras gunicorn corría con workers sync (una petición por proceso), pero ese
        # supuesto dejó de valer al pasar a gthread con 4 hilos (hallazgo S-07): con la
        # instancia única que creaba urls.py, dos peticiones concurrentes se pisaban la
        # request y el enclosure podía salir con el host de la otra. Por eso el feed se
        # registra ahora mediante `recordings_feed`, que instancia por petición.
        self.request = request
        return super().get_feed(obj, request)

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
        # URL ABSOLUTA (esquema+host): los clientes de podcast exigen que el enclosure
        # sea resoluble; una URL relativa deja el episodio sin audio en Apple/Spotify.
        return self.request.build_absolute_uri(item.file.url) if item.file else None

    def item_enclosure_length(self, item):
        try:
            return item.file.size if item.file else None
        except OSError:
            return 0

    def item_enclosure_mime_type(self, item):
        if not item.file:
            return None
        return mimetypes.guess_type(item.file.name)[0] or "audio/mpeg"


def recordings_feed(request, *args, **kwargs):
    """Vista del feed: crea una instancia NUEVA por petición.

    `path("feed/registros/", RecordingsFeed(), ...)` construía una sola instancia
    compartida por todo el proceso. Como el feed guarda la request en `self` (ver
    `get_feed`), dos peticiones concurrentes en el mismo worker se la pisaban. Con
    workers de tipo sync no ocurría; con gthread y 4 hilos, sí.
    """
    return RecordingsFeed()(request, *args, **kwargs)
