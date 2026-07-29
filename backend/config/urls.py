from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.content.feeds import LatestArticlesFeed
from apps.content.sitemaps import SITEMAPS
from apps.content.views import healthz, readyz, robots
from apps.media.feeds import recordings_feed

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("feed/", LatestArticlesFeed(), name="feed"),
    # Instancia por petición (no `RecordingsFeed()`): el feed guarda la request en la
    # instancia para el enclosure absoluto, y una instancia compartida se pisa entre
    # peticiones concurrentes desde que gunicorn usa hilos. Ver apps/media/feeds.py.
    path("feed/registros/", recordings_feed, name="recordings_feed"),
    path("robots.txt", robots, name="robots"),
    path("", include("apps.people.urls")),
    path("", include("apps.media.urls")),
    path("", include("apps.agenda.urls")),
    path("", include("apps.showcase.urls")),
    path("", include("apps.community.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.submissions.urls")),
    path("", include("apps.content.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Títulos del panel editorial
admin.site.site_header = "Reseñas — Panel editorial"
admin.site.site_title = "Reseñas"
admin.site.index_title = "Administración"
