from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Article, EditorialStatus


class LatestArticlesFeed(Feed):
    """RSS de textos publicados.

    El título y la descripción salían escritos a fuego y decían «Reseñas — Revista
    literaria», identidad anterior al giro a colectivo de poesía. Como no consultaban
    `SiteProfile`, configurar la identidad en el panel —tarea pendiente— no habría
    cambiado el feed: el desajuste habría sobrevivido en silencio a lo que debía
    arreglarlo. Ahora lee del perfil, como ya hacía el feed de podcast.
    """

    link = "/"

    # Respaldo si el perfil no tiene lema: el feed nunca debe quedarse sin descripción.
    DESCRIPCION_POR_DEFECTO = "Últimas reseñas, ensayos y entrevistas."

    def _perfil(self):
        from apps.showcase.models import SiteProfile

        return SiteProfile.load()

    def title(self, obj=None):
        perfil = self._perfil()
        # «Nombre — lema»; sin lema, solo el nombre (nada de un guion suelto al final).
        return f"{perfil.name} — {perfil.tagline}" if perfil.tagline else perfil.name

    def description(self, obj=None):
        return self._perfil().tagline or self.DESCRIPCION_POR_DEFECTO

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
