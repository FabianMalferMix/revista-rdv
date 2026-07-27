"""Feed podcast: registros de audio publicados (enclosure cuando hay archivo)."""

import mimetypes

from django.contrib.syndication.views import Feed

from .models import Recording


class RecordingsFeed(Feed):
    title = "Registros — lecturas del colectivo"
    link = "/registros/"
    description = "Registros en audio de lecturas y recitales."

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
