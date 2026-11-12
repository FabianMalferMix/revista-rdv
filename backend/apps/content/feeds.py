from django.contrib.syndication.views import Feed
from django.urls import reverse

from apps.showcase.profile import request_profile
from config.feeds import stable_guid
from config.origin import absolute_url

from .models import Article


class LatestArticlesFeed(Feed):
    """RSS de textos publicados.

    El título y la descripción salían escritos a fuego y decían «Reseñas — Revista
    literaria», identidad anterior al giro a colectivo de poesía. Como no consultaban
    `SiteProfile`, configurar la identidad en el panel —tarea pendiente— no habría
    cambiado el feed: el desajuste habría sobrevivido en silencio a lo que debía
    arreglarlo. Ahora lee del perfil, como ya hacía el feed de podcast.
    """

    # Respaldo si el perfil no tiene lema: el feed nunca debe quedarse sin descripción.
    DESCRIPCION_POR_DEFECTO = "Últimas reseñas, ensayos y entrevistas."

    def get_object(self, request):
        # El perfil llega a cada método como `obj`: la instancia se comparte entre hilos y no
        # guarda nada de la petición.
        return request_profile(request)

    def link(self):
        return absolute_url(reverse("site:home"))

    def feed_url(self):
        return absolute_url(reverse("feed"))

    def title(self, perfil):
        # «Nombre — lema»; sin lema, solo el nombre (nada de un guion suelto al final).
        return f"{perfil.site_name} — {perfil.tagline}" if perfil.tagline else perfil.site_name

    def description(self, perfil):
        return perfil.tagline or self.DESCRIPCION_POR_DEFECTO

    def items(self):
        # Solo lo que escribe cada ítem: la fila entera lleva el cuerpo del texto.
        return (
            Article.objects.published()
            .select_related("section")
            .only("slug", "title", "subtitle", "excerpt", "published_at", "section__name")
            .prefetch_related(Article.bylines_prefetch())[:20]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.subtitle or item.excerpt

    def item_link(self, item):
        # Absoluta desde SITE_URL: así Django no le añade el Host de la petición.
        return absolute_url(item.get_absolute_url())

    # El GUID no es la dirección: no cambia con el slug ni con el dominio.
    item_guid_is_permalink = False

    def item_guid(self, item):
        return stable_guid("article", item.pk)

    def item_pubdate(self, item):
        return item.published_at

    def item_author_name(self, item):
        names = [a.display_name for a in item.bylines]
        return ", ".join(names) if names else None

    def item_categories(self, item):
        return [item.section.name] if item.section else []
